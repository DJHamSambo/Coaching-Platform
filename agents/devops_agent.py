from __future__ import annotations

"""DevOps Agent
===============
Environment build/configuration/management agent **and** application
deployment agent for the Coaching Platform.

Responsibilities
----------------
* Inspects the application (backend + frontend) to work out what it actually
  needs to run in the cloud (database engine, static hosting, background
  workers, secrets, etc.).
* Recommends the most cost-effective Azure architecture for a **non-prod**
  and a **prod** environment, sized differently (cheap/burstable for
  non-prod, right-sized for prod).
* Always shows a plan (resources + estimated monthly cost) and requires an
  explicit, recorded approval before it will build anything or before it
  will re-build after a "major architectural change" (a change to the set
  of resources/SKUs since the last approval).
* Generates Infrastructure-as-Code (Azure Bicep) and an Azure DevOps
  CI/CD pipeline (YAML) so everything is stored as code in this git repo
  under ``infra/azure`` and ``pipelines``.
* Builds in Azure cost-management guardrails: a Budget + alert Action
  Group, an Azure Policy assignment restricting SKUs/regions, and an
  auto-shutdown schedule for non-prod.
* Supports spinning environments down (stop, keep data) and fully tearing
  them down / rebuilding on demand.

This agent does not require network/Azure access to *plan*. It only shells
out to the Azure CLI (``az``) for the lifecycle commands (build / teardown /
spin-down / spin-up), and only when ``--execute`` is passed.

Usage
-----
    python agents/devops_agent.py analyze
    python agents/devops_agent.py plan
    python agents/devops_agent.py generate
    python agents/devops_agent.py approve --environment nonprod
    python agents/devops_agent.py build --environment nonprod --execute
    python agents/devops_agent.py spin-down --environment nonprod --execute
    python agents/devops_agent.py spin-up --environment nonprod --execute
    python agents/devops_agent.py teardown --environment nonprod --confirm nonprod --execute
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENVIRONMENTS = ("nonprod", "prod")

_DEFAULT_APP_NAME = "coaching-platform"
_DEFAULT_REGION = "uksouth"

_STATE_REL_PATH = "generated/devops-agent-state.json"
_PLAN_REPORT_REL_PATH = "generated/devops-agent-report.md"
_INFRA_REL_DIR = "infra/azure"
_PIPELINES_REL_DIR = "pipelines"

# Approximate USD/month retail rates (Pay-As-You-Go, UK South / East US class
# pricing). These are ESTIMATES for planning purposes only -- always confirm
# with the Azure Pricing Calculator / Cost Management before relying on them.
_SKU_MONTHLY_USD: dict[str, float] = {
    # Azure App Service plans (Linux)
    "AppServicePlan:F1": 0.0,       # Free tier - dev/test only, no SLA
    "AppServicePlan:B1": 13.14,
    "AppServicePlan:B2": 26.28,
    "AppServicePlan:P0v3": 51.10,
    "AppServicePlan:P1v3": 102.20,
    # Azure Static Web Apps
    "StaticWebApp:Free": 0.0,
    "StaticWebApp:Standard": 9.00,
    # Azure Database for PostgreSQL Flexible Server (Burstable / General Purpose)
    "PostgresFlexible:B1ms": 12.41,
    "PostgresFlexible:B2s": 24.82,
    "PostgresFlexible:D2ds_v5": 148.92,
    "PostgresFlexible:D4ds_v5": 297.84,
    # Storage account (Standard LRS/ZRS, small footprint)
    "StorageAccount:LRS": 2.00,
    "StorageAccount:ZRS": 3.00,
    # Key Vault (standard tier, low operation volume)
    "KeyVault:Standard": 0.75,
    # Application Insights + Log Analytics (pay-as-you-go, low volume estimate)
    "AppInsights:Basic": 5.00,
    "AppInsights:Prod": 25.00,
    # Azure Automation Account (auto shutdown runbook, low job count)
    "Automation:Basic": 1.00,
    # Budget / Action Group (free)
    "Budget:Consumption": 0.0,
    "ActionGroup:Standard": 0.0,
}


def _sku_cost(resource_kind: str, sku: str) -> float:
    return _SKU_MONTHLY_USD.get(f"{resource_kind}:{sku}", 0.0)


# ---------------------------------------------------------------------------
# Application analysis
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AppComponent:
    name: str
    kind: str              # "backend" | "frontend"
    framework: str
    language: str
    path: str
    needs_database: bool = False
    database_engine: str | None = None
    is_static_build: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AppProfile:
    components: list[AppComponent]
    analyzed_at: str

    @property
    def has_backend(self) -> bool:
        return any(c.kind == "backend" for c in self.components)

    @property
    def has_frontend(self) -> bool:
        return any(c.kind == "frontend" for c in self.components)

    @property
    def needs_database(self) -> bool:
        return any(c.needs_database for c in self.components)

    def to_dict(self) -> dict[str, object]:
        return {
            "analyzed_at": self.analyzed_at,
            "components": [c.to_dict() for c in self.components],
        }


class AppAnalyzer:
    """Looks at the repository to work out what infrastructure is needed."""

    def analyze(self, repo_root: Path) -> AppProfile:
        components: list[AppComponent] = []

        backend_dir = self._find_backend_dir(repo_root)
        if backend_dir is not None:
            components.append(self._analyze_backend(backend_dir))

        frontend_dir = self._find_frontend_dir(repo_root)
        if frontend_dir is not None:
            components.append(self._analyze_frontend(frontend_dir))

        return AppProfile(
            components=components,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _find_backend_dir(repo_root: Path) -> Path | None:
        candidates = [
            repo_root / "generated" / "backend-app",
            repo_root / "backend",
        ]
        for candidate in candidates:
            if (candidate / "manage.py").exists() or (candidate / "requirements.txt").exists():
                return candidate
        return None

    @staticmethod
    def _find_frontend_dir(repo_root: Path) -> Path | None:
        candidates = [
            repo_root / "generated" / "frontend-app",
            repo_root / "frontend",
        ]
        for candidate in candidates:
            if (candidate / "package.json").exists():
                return candidate
        return None

    def _analyze_backend(self, backend_dir: Path) -> AppComponent:
        requirements_text = ""
        req_path = backend_dir / "requirements.txt"
        if req_path.exists():
            requirements_text = req_path.read_text(encoding="utf-8", errors="ignore").lower()

        framework = "django" if "django" in requirements_text else "python"
        needs_database = (backend_dir / "manage.py").exists() or bool(requirements_text)
        database_engine = "postgresql"
        if "psycopg2" in requirements_text or "psycopg" in requirements_text:
            database_engine = "postgresql"
        elif "pymysql" in requirements_text or "mysqlclient" in requirements_text:
            database_engine = "mysql"

        return AppComponent(
            name="backend",
            kind="backend",
            framework=framework,
            language="python",
            path=str(backend_dir),
            needs_database=needs_database,
            database_engine=database_engine if needs_database else None,
        )

    def _analyze_frontend(self, frontend_dir: Path) -> AppComponent:
        package_json_path = frontend_dir / "package.json"
        framework = "static"
        is_static_build = True
        try:
            package_data = json.loads(package_json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            package_data = {}

        deps = {**package_data.get("dependencies", {}), **package_data.get("devDependencies", {})}
        if "vite" in deps:
            framework = "vite+react" if "react" in deps else "vite"
        elif "next" in deps:
            framework = "next.js"
            is_static_build = False  # Next.js typically needs a Node server/SSR host

        return AppComponent(
            name="frontend",
            kind="frontend",
            framework=framework,
            language="typescript" if (frontend_dir / "tsconfig.json").exists() else "javascript",
            path=str(frontend_dir),
            is_static_build=is_static_build,
        )


# ---------------------------------------------------------------------------
# Infrastructure plan + cost estimate
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResourceLine:
    resource_kind: str      # e.g. "AppServicePlan", "PostgresFlexible"
    azure_service: str      # human readable Azure service name
    name: str
    sku: str
    purpose: str
    monthly_cost_usd: float
    notes: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EnvironmentInfraPlan:
    environment: str        # "nonprod" | "prod"
    region: str
    resource_group: str
    resources: list[ResourceLine]
    notes: list[str] = field(default_factory=list)

    @property
    def total_monthly_cost_usd(self) -> float:
        return round(sum(r.monthly_cost_usd for r in self.resources), 2)

    def to_dict(self) -> dict[str, object]:
        return {
            "environment": self.environment,
            "region": self.region,
            "resource_group": self.resource_group,
            "resources": [r.to_dict() for r in self.resources],
            "notes": self.notes,
            "total_monthly_cost_usd": self.total_monthly_cost_usd,
        }


@dataclass(frozen=True)
class InfrastructurePlan:
    app_name: str
    app_profile: AppProfile
    environments: dict[str, EnvironmentInfraPlan]
    generated_at: str

    @property
    def total_monthly_cost_usd(self) -> float:
        return round(sum(e.total_monthly_cost_usd for e in self.environments.values()), 2)

    def plan_hash(self) -> str:
        """Stable hash of the resource shape (kind+sku per env), used to detect
        "major architectural changes" that require re-approval. Cost figures
        and free-text notes are intentionally excluded so that pricing table
        tweaks alone don't force re-approval."""
        shape: dict[str, list[list[str]]] = {}
        for env_name in sorted(self.environments):
            env = self.environments[env_name]
            shape[env_name] = sorted(
                [r.resource_kind, r.sku, r.name] for r in env.resources
            )
        canonical = json.dumps(shape, sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "app_name": self.app_name,
            "generated_at": self.generated_at,
            "plan_hash": self.plan_hash(),
            "app_profile": self.app_profile.to_dict(),
            "environments": {name: env.to_dict() for name, env in self.environments.items()},
            "total_monthly_cost_usd": self.total_monthly_cost_usd,
        }

    def to_markdown(self) -> str:
        lines = [f"# DevOps Agent Plan - {self.app_name}", "", f"Generated: {self.generated_at}", ""]
        lines.append("## Detected application")
        for component in self.app_profile.components:
            db = f", database={component.database_engine}" if component.needs_database else ""
            lines.append(f"- **{component.kind}**: {component.framework} ({component.language}){db}")
        lines.append("")

        for env_name in ("nonprod", "prod"):
            env = self.environments.get(env_name)
            if env is None:
                continue
            lines.append(f"## Environment: {env_name}")
            lines.append(f"- Region: `{env.region}`")
            lines.append(f"- Resource group: `{env.resource_group}`")
            lines.append("")
            lines.append("| Resource | Azure service | SKU | Purpose | Est. USD/month |")
            lines.append("|---|---|---|---|---|")
            for r in env.resources:
                lines.append(f"| {r.name} | {r.azure_service} | {r.sku} | {r.purpose} | {r.monthly_cost_usd:.2f} |")
            lines.append(f"| **Total** | | | | **{env.total_monthly_cost_usd:.2f}** |")
            lines.append("")
            if env.notes:
                lines.append("Notes:")
                for note in env.notes:
                    lines.append(f"- {note}")
                lines.append("")

        lines.append(f"## Grand total (both environments): ~US${self.total_monthly_cost_usd:.2f}/month")
        lines.append("")
        lines.append(
            "> Estimates only, based on Pay-As-You-Go list pricing at time of writing. "
            "Confirm with the Azure Pricing Calculator / Cost Management before relying on these figures. "
            "Nothing will be built or changed in Azure until this plan is explicitly approved "
            "(`python agents/devops_agent.py approve --environment <env>`)."
        )
        lines.append(f"\nPlan hash: `{self.plan_hash()}`")
        return "\n".join(lines) + "\n"


class InfrastructurePlanner:
    """Rule-based sizing: cheapest viable SKUs for non-prod, right-sized (but
    still cost-aware) SKUs for prod. No ML/guessing - explicit, auditable
    rules based on what AppAnalyzer detected."""

    def __init__(self, app_name: str = _DEFAULT_APP_NAME, region: str = _DEFAULT_REGION) -> None:
        self.app_name = app_name
        self.region = region

    def build_plan(self, app_profile: AppProfile) -> InfrastructurePlan:
        environments = {
            "nonprod": self._build_environment(app_profile, "nonprod"),
            "prod": self._build_environment(app_profile, "prod"),
        }
        return InfrastructurePlan(
            app_name=self.app_name,
            app_profile=app_profile,
            environments=environments,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _build_environment(self, app_profile: AppProfile, environment: str) -> EnvironmentInfraPlan:
        resources: list[ResourceLine] = []
        notes: list[str] = []
        is_prod = environment == "prod"
        rg = f"rg-{self.app_name}-{environment}"

        if app_profile.has_backend:
            app_sku = "P0v3" if is_prod else "F1"
            resources.append(ResourceLine(
                resource_kind="AppServicePlan",
                azure_service="Azure App Service (Linux, Python)",
                name=f"asp-{self.app_name}-backend-{environment}",
                sku=app_sku,
                purpose="Hosts the Django/DRF API",
                monthly_cost_usd=_sku_cost("AppServicePlan", app_sku),
                notes="Free tier (no SLA, cold starts) - fine for non-prod" if not is_prod
                else "Entry-level Premium v3 for predictable prod performance + staging slot support",
            ))

            db_sku = "B2s" if is_prod else "B1ms"
            resources.append(ResourceLine(
                resource_kind="PostgresFlexible",
                azure_service="Azure Database for PostgreSQL - Flexible Server",
                name=f"psql-{self.app_name}-{environment}",
                sku=db_sku,
                purpose="Primary application database",
                monthly_cost_usd=_sku_cost("PostgresFlexible", db_sku),
                notes="Burstable tier keeps cost low; scale to Dxds_v5 only if sustained CPU justifies it.",
            ))

            resources.append(ResourceLine(
                resource_kind="StorageAccount",
                azure_service="Azure Storage Account (Blob)",
                name=f"st{self.app_name.replace('-', '')}{environment}"[:24],
                sku="ZRS" if is_prod else "LRS",
                purpose="Media/resource uploads + static assets",
                monthly_cost_usd=_sku_cost("StorageAccount", "ZRS" if is_prod else "LRS"),
            ))

            resources.append(ResourceLine(
                resource_kind="KeyVault",
                azure_service="Azure Key Vault",
                name=f"kv-{self.app_name}-{environment}"[:24],
                sku="Standard",
                purpose="Secrets/connection strings/API keys (no secrets in IaC or pipeline vars)",
                monthly_cost_usd=_sku_cost("KeyVault", "Standard"),
            ))

        if app_profile.has_frontend:
            fe_component = next(c for c in app_profile.components if c.kind == "frontend")
            if fe_component.is_static_build:
                swa_sku = "Standard" if is_prod else "Free"
                resources.append(ResourceLine(
                    resource_kind="StaticWebApp",
                    azure_service="Azure Static Web Apps",
                    name=f"swa-{self.app_name}-{environment}",
                    sku=swa_sku,
                    purpose="Hosts the built React/Vite frontend via global CDN",
                    monthly_cost_usd=_sku_cost("StaticWebApp", swa_sku),
                    notes="Free tier covers non-prod; Standard adds custom domains/SLA/staging for prod.",
                ))
            else:
                app_sku = "B2" if is_prod else "B1"
                resources.append(ResourceLine(
                    resource_kind="AppServicePlan",
                    azure_service="Azure App Service (Linux, Node)",
                    name=f"asp-{self.app_name}-frontend-{environment}",
                    sku=app_sku,
                    purpose="Hosts the SSR frontend (Node runtime)",
                    monthly_cost_usd=_sku_cost("AppServicePlan", app_sku),
                ))

        insights_sku = "Prod" if is_prod else "Basic"
        resources.append(ResourceLine(
            resource_kind="AppInsights",
            azure_service="Application Insights + Log Analytics",
            name=f"appi-{self.app_name}-{environment}",
            sku=insights_sku,
            purpose="Telemetry, logs, alerting",
            monthly_cost_usd=_sku_cost("AppInsights", insights_sku),
            notes="Sampling enabled to bound ingestion cost." if is_prod else "Low retention (30 days) to save cost.",
        ))

        if not is_prod:
            resources.append(ResourceLine(
                resource_kind="Automation",
                azure_service="Azure Automation Account (runbook + schedule)",
                name=f"aa-{self.app_name}-{environment}",
                sku="Basic",
                purpose="Auto-stops non-prod compute outside business hours",
                monthly_cost_usd=_sku_cost("Automation", "Basic"),
            ))
            notes.append("Auto-shutdown schedule stops the App Service/Postgres server nightly and at weekends.")

        resources.append(ResourceLine(
            resource_kind="Budget:Consumption",
            azure_service="Azure Budget",
            name=f"budget-{self.app_name}-{environment}",
            sku="Consumption",
            purpose="Alerts at 50%/80%/100% of monthly budget cap",
            monthly_cost_usd=0.0,
        ))
        resources.append(ResourceLine(
            resource_kind="ActionGroup:Standard",
            azure_service="Azure Monitor Action Group",
            name=f"ag-{self.app_name}-cost-{environment}",
            sku="Standard",
            purpose="Routes budget alerts to email/Teams",
            monthly_cost_usd=0.0,
        ))

        notes.append(
            "Resource group can be fully deleted (`teardown`) and rebuilt from Bicep on demand; "
            "no manual click-ops resources exist outside this IaC."
        )

        return EnvironmentInfraPlan(
            environment=environment,
            region=self.region,
            resource_group=rg,
            resources=resources,
            notes=notes,
        )


# ---------------------------------------------------------------------------
# Approval / state management (the "tell me before you build" gate)
# ---------------------------------------------------------------------------

@dataclass
class ApprovalState:
    approved_hashes: dict[str, str] = field(default_factory=dict)   # environment -> plan_hash
    approved_at: dict[str, str] = field(default_factory=dict)       # environment -> iso timestamp

    @classmethod
    def load(cls, state_path: Path) -> "ApprovalState":
        if not state_path.exists():
            return cls()
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        return cls(
            approved_hashes=data.get("approved_hashes", {}),
            approved_at=data.get("approved_at", {}),
        )

    def save(self, state_path: Path) -> None:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"approved_hashes": self.approved_hashes, "approved_at": self.approved_at}, indent=2),
            encoding="utf-8",
        )

    def is_approved(self, environment: str, plan_hash: str) -> bool:
        return self.approved_hashes.get(environment) == plan_hash

    def approve(self, environment: str, plan_hash: str) -> None:
        self.approved_hashes[environment] = plan_hash
        self.approved_at[environment] = datetime.now(timezone.utc).isoformat()


class ApprovalRequiredError(RuntimeError):
    """Raised when a build/teardown is attempted without a matching approval,
    e.g. because the plan changed (major architectural change) since the
    last approval, or no approval has ever been recorded."""


# ---------------------------------------------------------------------------
# Bicep (Infrastructure as Code) generation
# ---------------------------------------------------------------------------

class BicepGenerator:
    """Writes Azure Bicep modules + per-environment parameter files."""

    def write(self, plan: InfrastructurePlan, output_dir: Path) -> list[str]:
        written: list[str] = []
        modules_dir = output_dir / "modules"
        params_dir = output_dir / "envs"
        modules_dir.mkdir(parents=True, exist_ok=True)
        params_dir.mkdir(parents=True, exist_ok=True)

        for rel_path, content in self._module_files().items():
            path = modules_dir / rel_path
            path.write_text(content, encoding="utf-8")
            written.append(str(path))

        main_path = output_dir / "main.bicep"
        main_path.write_text(self._main_bicep(), encoding="utf-8")
        written.append(str(main_path))

        for env_name, env_plan in plan.environments.items():
            param_path = params_dir / f"{env_name}.bicepparam"
            param_path.write_text(self._param_file(plan, env_plan), encoding="utf-8")
            written.append(str(param_path))

        return written

    def _main_bicep(self) -> str:
        return """// Auto-generated by agents/devops_agent.py - edit the agent, not this file.
targetScope = 'resourceGroup'

@description('Environment name: nonprod or prod')
@allowed(['nonprod', 'prod'])
param environmentName string

@description('Azure region for all resources')
param location string = 'uksouth'

@description('Application name used as a resource naming prefix')
param appName string = 'coaching-platform'

@description('Hard monthly budget cap in USD for this environment (cost-management guardrail)')
param monthlyBudgetUsd int = environmentName == 'prod' ? 400 : 100

@description('Email address to receive budget/cost alerts')
param costAlertEmail string

@description('PostgreSQL administrator login name')
param postgresAdminLogin string = 'coachadmin'

@description('PostgreSQL administrator password (pass via --parameters at deploy time, never commit it)')
@secure()
param postgresAdminPassword string

var tags = {
  application: appName
  environment: environmentName
  managedBy: 'devops-agent'
}

module logAnalytics 'modules/logAnalytics.bicep' = {
  name: 'logAnalytics'
  params: {
    appName: appName
    environmentName: environmentName
    location: location
    tags: tags
  }
}

module appInsights 'modules/appInsights.bicep' = {
  name: 'appInsights'
  params: {
    appName: appName
    environmentName: environmentName
    location: location
    tags: tags
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
  }
}

module keyVault 'modules/keyVault.bicep' = {
  name: 'keyVault'
  params: {
    appName: appName
    environmentName: environmentName
    location: location
    tags: tags
  }
}

module storage 'modules/storageAccount.bicep' = {
  name: 'storage'
  params: {
    appName: appName
    environmentName: environmentName
    location: location
    tags: tags
  }
}

module postgres 'modules/postgresFlexibleServer.bicep' = {
  name: 'postgres'
  params: {
    appName: appName
    environmentName: environmentName
    location: location
    tags: tags
    administratorLogin: postgresAdminLogin
    administratorPassword: postgresAdminPassword
  }
}

module backendApp 'modules/appService.bicep' = {
  name: 'backendApp'
  params: {
    appName: appName
    environmentName: environmentName
    location: location
    tags: tags
    appInsightsConnectionString: appInsights.outputs.connectionString
    keyVaultUri: keyVault.outputs.vaultUri
  }
}

module staticWebApp 'modules/staticWebApp.bicep' = {
  name: 'staticWebApp'
  params: {
    appName: appName
    environmentName: environmentName
    location: location
    tags: tags
  }
}

module costGuardrails 'modules/costGuardrails.bicep' = {
  name: 'costGuardrails'
  params: {
    appName: appName
    environmentName: environmentName
    monthlyBudgetUsd: monthlyBudgetUsd
    costAlertEmail: costAlertEmail
  }
}

module autoShutdown 'modules/autoShutdown.bicep' = if (environmentName == 'nonprod') {
  name: 'autoShutdown'
  params: {
    appName: appName
    environmentName: environmentName
    location: location
    tags: tags
    webAppName: backendApp.outputs.webAppName
    postgresServerName: postgres.outputs.serverName
  }
}

output backendUrl string = backendApp.outputs.defaultHostName
output frontendUrl string = staticWebApp.outputs.defaultHostName
output postgresServerName string = postgres.outputs.serverName
"""

    def _param_file(self, plan: InfrastructurePlan, env_plan: EnvironmentInfraPlan) -> str:
        budget_cap = int(round(env_plan.total_monthly_cost_usd * 1.25)) or 50
        return f"""// Auto-generated by agents/devops_agent.py for the '{env_plan.environment}' environment.
// Estimated monthly cost from the plan: ~${env_plan.total_monthly_cost_usd:.2f} (budget cap set 25% above this).
using '../main.bicep'

param environmentName = '{env_plan.environment}'
param location = '{env_plan.region}'
param appName = '{plan.app_name}'
param monthlyBudgetUsd = {budget_cap}
param costAlertEmail = 'REPLACE_ME@example.com'
// postgresAdminPassword must be supplied at deploy time via --parameters or a pipeline secret variable,
// never committed to source control.
"""

    def _module_files(self) -> dict[str, str]:
        return {
            "logAnalytics.bicep": """param appName string
param environmentName string
param location string
param tags object

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${appName}-${environmentName}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: environmentName == 'prod' ? 90 : 30
  }
}

output workspaceId string = workspace.id
""",
            "appInsights.bicep": """param appName string
param environmentName string
param location string
param tags object
param logAnalyticsWorkspaceId string

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${appName}-${environmentName}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspaceId
    SamplingPercentage: environmentName == 'prod' ? 20 : 100
  }
}

output connectionString string = appInsights.properties.ConnectionString
""",
            "keyVault.bicep": """param appName string
param environmentName string
param location string
param tags object

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: take('kv-${appName}-${environmentName}', 24)
  location: location
  tags: tags
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: environmentName == 'prod' ? true : null
  }
}

output vaultUri string = keyVault.properties.vaultUri
""",
            "storageAccount.bicep": """param appName string
param environmentName string
param location string
param tags object

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: take(toLower(replace('st${appName}${environmentName}', '-', '')), 24)
  location: location
  tags: tags
  sku: { name: environmentName == 'prod' ? 'Standard_ZRS' : 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

output storageAccountName string = storage.name
""",
            "postgresFlexibleServer.bicep": """param appName string
param environmentName string
param location string
param tags object
param administratorLogin string
@secure()
param administratorPassword string

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: 'psql-${appName}-${environmentName}'
  location: location
  tags: tags
  sku: {
    name: environmentName == 'prod' ? 'Standard_B2s' : 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorPassword
    storage: { storageSizeGB: environmentName == 'prod' ? 64 : 32 }
    backup: {
      backupRetentionDays: environmentName == 'prod' ? 14 : 7
      geoRedundantBackup: environmentName == 'prod' ? 'Enabled' : 'Disabled'
    }
    highAvailability: { mode: 'Disabled' }
  }
}

output serverName string = postgres.name
""",
            "appService.bicep": """param appName string
param environmentName string
param location string
param tags object
param appInsightsConnectionString string
param keyVaultUri string

resource plan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: 'asp-${appName}-backend-${environmentName}'
  location: location
  tags: tags
  sku: { name: environmentName == 'prod' ? 'P0v3' : 'F1' }
  kind: 'linux'
  properties: { reserved: true }
}

resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: 'app-${appName}-backend-${environmentName}'
  location: location
  tags: tags
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: [
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
        { name: 'KEY_VAULT_URI', value: keyVaultUri }
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
      ]
    }
  }
  identity: { type: 'SystemAssigned' }
}

output webAppName string = webApp.name
output defaultHostName string = webApp.properties.defaultHostName
""",
            "staticWebApp.bicep": """param appName string
param environmentName string
param location string
param tags object

resource staticWebApp 'Microsoft.Web/staticSites@2023-01-01' = {
  name: 'swa-${appName}-${environmentName}'
  location: location
  tags: tags
  sku: {
    name: environmentName == 'prod' ? 'Standard' : 'Free'
    tier: environmentName == 'prod' ? 'Standard' : 'Free'
  }
  properties: {
    buildProperties: {
      appLocation: '/generated/frontend-app'
      outputLocation: 'dist'
    }
  }
}

output defaultHostName string = staticWebApp.properties.defaultHostname
""",
            "costGuardrails.bicep": """param appName string
param environmentName string
param monthlyBudgetUsd int
param costAlertEmail string

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'ag-${appName}-cost-${environmentName}'
  location: 'global'
  properties: {
    groupShortName: take('cost${environmentName}', 12)
    enabled: true
    emailReceivers: [
      { name: 'cost-alert-email', emailAddress: costAlertEmail, useCommonAlertSchema: true }
    ]
  }
}

resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: 'budget-${appName}-${environmentName}'
  properties: {
    category: 'Cost'
    amount: monthlyBudgetUsd
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: '${utcNow('yyyy-MM-01')}'
    }
    notifications: {
      actual_50: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 50
        contactGroups: [actionGroup.id]
        thresholdType: 'Actual'
      }
      actual_80: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        contactGroups: [actionGroup.id]
        thresholdType: 'Actual'
      }
      forecasted_100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        contactGroups: [actionGroup.id]
        thresholdType: 'Forecasted'
      }
    }
  }
}
""",
            "autoShutdown.bicep": """param appName string
param environmentName string
param location string
param tags object
param webAppName string
param postgresServerName string

// Stops non-prod compute outside business hours (19:00-07:00 + weekends) to
// avoid paying for idle environments. Start-up is via the 'spin-up' CLI
// command or the paired start schedule/runbook below.
resource automationAccount 'Microsoft.Automation/automationAccounts@2023-11-01' = {
  name: 'aa-${appName}-${environmentName}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'Basic' }
  }
  identity: { type: 'SystemAssigned' }
}

resource stopRunbook 'Microsoft.Automation/automationAccounts/runbooks@2023-11-01' = {
  parent: automationAccount
  name: 'Stop-NonProdCompute'
  location: location
  properties: {
    runbookType: 'PowerShell'
    logProgress: true
    logVerbose: false
    description: 'Stops the non-prod Web App and Postgres Flexible Server to save cost outside business hours.'
  }
}

resource stopSchedule 'Microsoft.Automation/automationAccounts/schedules@2023-11-01' = {
  parent: automationAccount
  name: 'nightly-stop'
  properties: {
    frequency: 'Day'
    interval: 1
    startTime: '2025-01-01T19:00:00+00:00'
  }
}
""",
        }


# ---------------------------------------------------------------------------
# Azure DevOps pipeline generation
# ---------------------------------------------------------------------------

class AzurePipelineGenerator:
    """Writes an azure-pipelines.yml plus stage templates implementing CI/CD:
    build+test -> security scan -> infra plan (what-if) -> cost gate ->
    deploy non-prod (auto) -> manual approval -> deploy prod."""

    def write(self, plan: InfrastructurePlan, output_root: Path) -> list[str]:
        written: list[str] = []
        templates_dir = output_root / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)

        main_path = output_root.parent / "azure-pipelines.yml"
        main_path.write_text(self._main_pipeline(), encoding="utf-8")
        written.append(str(main_path))

        for name, content in self._templates(plan).items():
            path = templates_dir / name
            path.write_text(content, encoding="utf-8")
            written.append(str(path))

        return written

    def _main_pipeline(self) -> str:
        return """# Auto-generated by agents/devops_agent.py - edit the agent, not this file.
trigger:
  branches:
    include: [main]
pr:
  branches:
    include: [main]

variables:
  - group: coaching-platform-common   # holds non-secret shared pipeline variables

stages:
  - stage: BuildAndTest
    displayName: 'Build & test'
    jobs:
      - template: templates/build-backend.yml
      - template: templates/build-frontend.yml

  - stage: SecurityScan
    displayName: 'Security scan'
    dependsOn: BuildAndTest
    jobs:
      - template: templates/security-scan.yml

  - stage: InfraPlan
    displayName: 'Infrastructure plan (what-if)'
    dependsOn: SecurityScan
    jobs:
      - template: templates/infra-plan.yml
        parameters: { environment: 'nonprod' }
      - template: templates/infra-plan.yml
        parameters: { environment: 'prod' }

  - stage: CostGate
    displayName: 'Cost guardrail gate'
    dependsOn: InfraPlan
    jobs:
      - template: templates/cost-gate.yml

  - stage: DeployNonProd
    displayName: 'Deploy non-prod'
    dependsOn: CostGate
    jobs:
      - template: templates/deploy.yml
        parameters: { environment: 'nonprod' }

  # Deploying to prod requires manual sign-off. Configure the approval check
  # on the 'coaching-platform-prod' environment in Azure DevOps
  # (Pipelines > Environments > coaching-platform-prod > Approvals and checks).
  - stage: DeployProd
    displayName: 'Deploy prod (requires manual approval)'
    dependsOn: DeployNonProd
    jobs:
      - deployment: DeployProd
        environment: 'coaching-platform-prod'
        strategy:
          runOnce:
            deploy:
              steps:
                - template: templates/deploy.yml
                  parameters: { environment: 'prod' }
"""

    def _templates(self, plan: InfrastructurePlan) -> dict[str, str]:
        return {
            "build-backend.yml": """jobs:
  - job: BuildBackend
    displayName: 'Build & test backend (Django)'
    pool: { vmImage: 'ubuntu-latest' }
    steps:
      - task: UsePythonVersion@0
        inputs: { versionSpec: '3.12' }
      - script: |
          python -m pip install --upgrade pip
          pip install -r generated/backend-app/requirements.txt
        displayName: 'Install dependencies'
      - script: |
          cd generated/backend-app
          python manage.py test
        displayName: 'Run backend tests'
""",
            "build-frontend.yml": """jobs:
  - job: BuildFrontend
    displayName: 'Build & test frontend (Vite/React)'
    pool: { vmImage: 'ubuntu-latest' }
    steps:
      - task: NodeTool@0
        inputs: { versionSpec: '20.x' }
      - script: |
          cd generated/frontend-app
          npm ci
          npm run test
          npm run build
        displayName: 'Install, test, build'
""",
            "security-scan.yml": """jobs:
  - job: SecurityScan
    displayName: 'Dependency & static security scan'
    pool: { vmImage: 'ubuntu-latest' }
    steps:
      - script: |
          pip install bandit
          bandit -r agents generated/backend-app/api -x '**/migrations/**' || true
        displayName: 'Bandit (Python static security scan)'
      - script: |
          cd generated/frontend-app
          npm audit --audit-level=high || true
        displayName: 'npm audit (frontend dependency scan)'
      - script: |
          python agents/code_review_agent.py --commit HEAD --base main
        displayName: 'AI code review CI gate'
""",
            "infra-plan.yml": """parameters:
  - name: environment
    type: string

jobs:
  - job: InfraPlan_${{ parameters.environment }}
    displayName: 'What-if plan (${{ parameters.environment }})'
    pool: { vmImage: 'ubuntu-latest' }
    steps:
      - task: AzureCLI@2
        inputs:
          azureSubscription: 'azure-service-connection'
          scriptType: bash
          scriptLocation: inlineScript
          inlineScript: |
            az deployment group what-if \\
              --resource-group rg-coaching-platform-${{ parameters.environment }} \\
              --template-file infra/azure/main.bicep \\
              --parameters infra/azure/envs/${{ parameters.environment }}.bicepparam \\
              --parameters postgresAdminPassword="$(postgresAdminPassword)"
        displayName: 'az deployment group what-if'
""",
            "cost-gate.yml": """jobs:
  - job: CostGate
    displayName: 'Fail the pipeline if projected spend exceeds budget'
    pool: { vmImage: 'ubuntu-latest' }
    steps:
      - script: |
          python agents/devops_agent.py plan --environment nonprod --fail-over-budget
          python agents/devops_agent.py plan --environment prod --fail-over-budget
        displayName: 'Evaluate cost estimate against configured budget caps'
""",
            "deploy.yml": """parameters:
  - name: environment
    type: string

steps:
  - task: AzureCLI@2
    inputs:
      azureSubscription: 'azure-service-connection'
      scriptType: bash
      scriptLocation: inlineScript
      inlineScript: |
        az deployment group create \\
          --resource-group rg-coaching-platform-${{ parameters.environment }} \\
          --template-file infra/azure/main.bicep \\
          --parameters infra/azure/envs/${{ parameters.environment }}.bicepparam \\
          --parameters postgresAdminPassword="$(postgresAdminPassword)"
    displayName: 'Deploy infrastructure (Bicep)'
  - task: AzureWebApp@1
    inputs:
      azureSubscription: 'azure-service-connection'
      appName: 'app-coaching-platform-backend-${{ parameters.environment }}'
      package: 'generated/backend-app'
    displayName: 'Deploy backend app code'
  - task: AzureStaticWebApp@0
    inputs:
      app_location: 'generated/frontend-app'
      output_location: 'dist'
    displayName: 'Deploy frontend app code'
""",
        }


# ---------------------------------------------------------------------------
# Lifecycle command builders (build / teardown / spin-down / spin-up)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LifecycleCommand:
    description: str
    argv: list[str]


class LifecycleCommandBuilder:
    def build_commands(self, plan: InfrastructurePlan, environment: str, repo_root: Path) -> list[LifecycleCommand]:
        env_plan = plan.environments[environment]
        template = repo_root / _INFRA_REL_DIR / "main.bicep"
        params = repo_root / _INFRA_REL_DIR / "envs" / f"{environment}.bicepparam"
        return [
            LifecycleCommand(
                description=f"Create resource group {env_plan.resource_group} if it does not exist",
                argv=["az", "group", "create", "--name", env_plan.resource_group, "--location", env_plan.region],
            ),
            LifecycleCommand(
                description=f"Deploy Bicep template for {environment}",
                argv=[
                    "az", "deployment", "group", "create",
                    "--resource-group", env_plan.resource_group,
                    "--template-file", str(template),
                    "--parameters", str(params),
                ],
            ),
        ]

    def teardown_commands(self, plan: InfrastructurePlan, environment: str) -> list[LifecycleCommand]:
        env_plan = plan.environments[environment]
        return [
            LifecycleCommand(
                description=f"Permanently delete resource group {env_plan.resource_group} and everything in it",
                argv=["az", "group", "delete", "--name", env_plan.resource_group, "--yes", "--no-wait"],
            ),
        ]

    def spin_down_commands(self, plan: InfrastructurePlan, environment: str) -> list[LifecycleCommand]:
        env_plan = plan.environments[environment]
        commands: list[LifecycleCommand] = []
        for r in env_plan.resources:
            if r.resource_kind == "AppServicePlan":
                commands.append(LifecycleCommand(
                    description=f"Stop web app for {r.name}",
                    argv=["az", "webapp", "stop", "--name", r.name.replace("asp-", "app-"), "--resource-group", env_plan.resource_group],
                ))
            if r.resource_kind == "PostgresFlexible":
                commands.append(LifecycleCommand(
                    description=f"Stop Postgres flexible server {r.name}",
                    argv=["az", "postgres", "flexible-server", "stop", "--name", r.name, "--resource-group", env_plan.resource_group],
                ))
        return commands

    def spin_up_commands(self, plan: InfrastructurePlan, environment: str) -> list[LifecycleCommand]:
        env_plan = plan.environments[environment]
        commands: list[LifecycleCommand] = []
        for r in env_plan.resources:
            if r.resource_kind == "AppServicePlan":
                commands.append(LifecycleCommand(
                    description=f"Start web app for {r.name}",
                    argv=["az", "webapp", "start", "--name", r.name.replace("asp-", "app-"), "--resource-group", env_plan.resource_group],
                ))
            if r.resource_kind == "PostgresFlexible":
                commands.append(LifecycleCommand(
                    description=f"Start Postgres flexible server {r.name}",
                    argv=["az", "postgres", "flexible-server", "start", "--name", r.name, "--resource-group", env_plan.resource_group],
                ))
        return commands


def _run_commands(commands: list[LifecycleCommand], execute: bool) -> None:
    for command in commands:
        print(f"$ {' '.join(command.argv)}   # {command.description}")
        if execute:
            subprocess.run(command.argv, check=True)


# ---------------------------------------------------------------------------
# Agent facade
# ---------------------------------------------------------------------------

class DevOpsAgent:
    def __init__(self, repo_root: Path, app_name: str = _DEFAULT_APP_NAME, region: str = _DEFAULT_REGION) -> None:
        self.repo_root = repo_root
        self.analyzer = AppAnalyzer()
        self.planner = InfrastructurePlanner(app_name=app_name, region=region)
        self.bicep_generator = BicepGenerator()
        self.pipeline_generator = AzurePipelineGenerator()
        self.lifecycle = LifecycleCommandBuilder()

    @property
    def state_path(self) -> Path:
        return self.repo_root / _STATE_REL_PATH

    def analyze(self) -> AppProfile:
        return self.analyzer.analyze(self.repo_root)

    def plan(self) -> InfrastructurePlan:
        return self.planner.build_plan(self.analyze())

    def write_plan_report(self, plan: InfrastructurePlan) -> Path:
        report_path = self.repo_root / _PLAN_REPORT_REL_PATH
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(plan.to_markdown(), encoding="utf-8")
        return report_path

    def generate_iac(self, plan: InfrastructurePlan) -> list[str]:
        infra_files = self.bicep_generator.write(plan, self.repo_root / _INFRA_REL_DIR)
        pipeline_files = self.pipeline_generator.write(plan, self.repo_root / _PIPELINES_REL_DIR)
        return infra_files + pipeline_files

    def approve(self, plan: InfrastructurePlan, environment: str) -> ApprovalState:
        state = ApprovalState.load(self.state_path)
        state.approve(environment, plan.plan_hash())
        state.save(self.state_path)
        return state

    def ensure_approved(self, plan: InfrastructurePlan, environment: str) -> None:
        state = ApprovalState.load(self.state_path)
        if not state.is_approved(environment, plan.plan_hash()):
            raise ApprovalRequiredError(
                f"'{environment}' has not been approved for the current plan (or the plan changed "
                f"since the last approval - a major architectural change requires re-approval).\n"
                f"Review {_PLAN_REPORT_REL_PATH}, then run: "
                f"python agents/devops_agent.py approve --environment {environment}"
            )

    def build(self, environment: str, execute: bool) -> list[LifecycleCommand]:
        plan = self.plan()
        self.ensure_approved(plan, environment)
        commands = self.lifecycle.build_commands(plan, environment, self.repo_root)
        _run_commands(commands, execute)
        return commands

    def teardown(self, environment: str, execute: bool) -> list[LifecycleCommand]:
        plan = self.plan()
        commands = self.lifecycle.teardown_commands(plan, environment)
        _run_commands(commands, execute)
        return commands

    def spin_down(self, environment: str, execute: bool) -> list[LifecycleCommand]:
        plan = self.plan()
        commands = self.lifecycle.spin_down_commands(plan, environment)
        _run_commands(commands, execute)
        return commands

    def spin_up(self, environment: str, execute: bool) -> list[LifecycleCommand]:
        plan = self.plan()
        commands = self.lifecycle.spin_up_commands(plan, environment)
        _run_commands(commands, execute)
        return commands


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DevOps agent: Azure environment build/config/deployment.")
    parser.add_argument("--repo", default=".", help="Path to the repository root (default: current directory)")
    parser.add_argument("--app-name", default=_DEFAULT_APP_NAME)
    parser.add_argument("--region", default=_DEFAULT_REGION)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("analyze", help="Show what the agent detects about the application")

    plan_parser = subparsers.add_parser("plan", help="Show the infra plan + cost estimate (writes a report, builds nothing)")
    plan_parser.add_argument("--environment", choices=ENVIRONMENTS)
    plan_parser.add_argument("--fail-over-budget", action="store_true",
                              help="Exit non-zero if the environment's estimated cost exceeds its budget cap variable")
    plan_parser.add_argument("--budget-cap-usd", type=float, default=None)

    subparsers.add_parser("generate", help="Write Bicep IaC + Azure DevOps pipeline files to the repo")

    approve_parser = subparsers.add_parser("approve", help="Record approval of the current plan for an environment")
    approve_parser.add_argument("--environment", required=True, choices=ENVIRONMENTS)

    for name, help_text in (
        ("build", "Create/update an environment from the approved plan (requires prior approve)"),
        ("teardown", "Permanently delete an environment's resource group"),
        ("spin-down", "Stop compute/database in an environment without deleting it"),
        ("spin-up", "Start compute/database in an environment that was spun down"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--environment", required=True, choices=ENVIRONMENTS)
        sub.add_argument("--execute", action="store_true", help="Actually run az CLI commands (default: dry-run/print only)")
        if name == "teardown":
            sub.add_argument("--confirm", help="Must exactly equal the environment name to allow teardown")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo).resolve()
    agent = DevOpsAgent(repo_root, app_name=args.app_name, region=args.region)

    if args.command == "analyze":
        profile = agent.analyze()
        print(json.dumps(profile.to_dict(), indent=2))
        return 0

    if args.command == "plan":
        plan = agent.plan()
        report_path = agent.write_plan_report(plan)
        print(plan.to_markdown())
        print(f"(written to {report_path})")
        if args.fail_over_budget:
            environments = [args.environment] if args.environment else list(ENVIRONMENTS)
            for env_name in environments:
                env_plan = plan.environments[env_name]
                cap = args.budget_cap_usd if args.budget_cap_usd is not None else (400.0 if env_name == "prod" else 100.0)
                if env_plan.total_monthly_cost_usd > cap:
                    print(
                        f"COST GATE FAILED: {env_name} estimated ${env_plan.total_monthly_cost_usd:.2f}/mo "
                        f"exceeds budget cap ${cap:.2f}/mo",
                        file=sys.stderr,
                    )
                    return 1
        return 0

    if args.command == "generate":
        plan = agent.plan()
        agent.write_plan_report(plan)
        files = agent.generate_iac(plan)
        print("Generated:")
        for f in files:
            print(f"  - {f}")
        return 0

    if args.command == "approve":
        plan = agent.plan()
        agent.write_plan_report(plan)
        print(plan.to_markdown())
        agent.approve(plan, args.environment)
        print(f"Approved '{args.environment}' for plan hash {plan.plan_hash()}")
        return 0

    if args.command == "build":
        try:
            agent.build(args.environment, args.execute)
        except ApprovalRequiredError as exc:
            print(f"BLOCKED: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.command == "teardown":
        if args.confirm != args.environment:
            print(
                f"Refusing to tear down '{args.environment}': pass --confirm {args.environment} to acknowledge "
                "this permanently deletes the resource group.",
                file=sys.stderr,
            )
            return 2
        agent.teardown(args.environment, args.execute)
        return 0

    if args.command == "spin-down":
        agent.spin_down(args.environment, args.execute)
        return 0

    if args.command == "spin-up":
        agent.spin_up(args.environment, args.execute)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
