# DevOps Agent

## Purpose

`agents/devops_agent.py` is the environment build/configuration/management
agent **and** application deployment agent for the Coaching Platform. It:

- Inspects the actual application code (backend + frontend) to work out what
  it needs to run in the cloud.
- Recommends the most cost-effective Azure architecture, sized separately for
  a **non-prod** and a **prod** environment.
- Always shows the plan and its estimated monthly cost, and refuses to build
  or make a major architectural change until that plan has been explicitly
  approved.
- Generates Azure Bicep (Infrastructure as Code) and an Azure DevOps
  CI/CD pipeline, both stored as code in this git repository.
- Bakes in Azure cost-management guardrails (budgets, alerts, an auto-shutdown
  schedule for non-prod).
- Lets you spin environments down (stop, keep data), or fully tear them down
  and rebuild them from scratch, on demand.

## What it does not do

It does not call Azure to *plan* — analysis and cost estimation are pure,
offline, rule-based logic. It only shells out to the `az` CLI for the
lifecycle commands (`build`, `teardown`, `spin-down`, `spin-up`), and only
when `--execute` is passed; otherwise every command prints what it *would*
run (dry-run by default).

## How application analysis works

`AppAnalyzer` looks for:

- A backend under `generated/backend-app` or `backend/` (detected via
  `manage.py` / `requirements.txt`). It reads `requirements.txt` to detect
  the framework (Django) and database driver (`psycopg2` → PostgreSQL,
  `pymysql`/`mysqlclient` → MySQL).
- A frontend under `generated/frontend-app` or `frontend/` (detected via
  `package.json`). It reads dependencies to detect Vite/React (static build,
  suitable for Azure Static Web Apps) vs Next.js (SSR, needs a Node host).

## How sizing works

`InfrastructurePlanner` applies explicit, auditable rules — no guessing:

| Component | Non-prod | Prod |
|---|---|---|
| Backend App Service | `F1` (free tier) | `P0v3` |
| PostgreSQL Flexible Server | `B1ms` (burstable) | `B2s` (burstable) |
| Storage Account | `LRS` | `ZRS` |
| Static Web App (frontend) | `Free` | `Standard` |
| Application Insights | Basic, 30-day retention | Prod, sampled, higher retention |
| Auto-shutdown Automation Account | Included | Not included (always-on) |
| Budget + Action Group | Included | Included |

Every resource carries an approximate USD/month cost from a static pricing
table in the agent (Pay-As-You-Go list pricing, clearly marked as an estimate
— always confirm with the Azure Pricing Calculator / Cost Management before
relying on it).

## The approval gate

Nothing is ever built or rebuilt without an explicit, recorded approval:

1. `plan` computes the current plan and writes
   `generated/devops-agent-report.md` with the full resource list, cost
   table, and a **plan hash** (a stable hash of resource kinds/SKUs/names,
   excluding cost figures and notes).
2. `approve --environment <env>` records that hash as approved for that
   environment in `generated/devops-agent-state.json`.
3. `build --environment <env>` recomputes the plan and refuses to proceed
   (`ApprovalRequiredError`, exit code 2) unless the freshly computed hash
   matches the approved one. If the detected application changes shape (e.g.
   a new component, or a SKU rule change) the hash changes and a **new**
   approval is required — this is how "major architectural changes" get a
   mandatory human sign-off before anything is touched in Azure.

## Infrastructure as Code

`generate` writes:

- `infra/azure/main.bicep` — resource-group-scoped template wiring together
  Log Analytics, Application Insights, Key Vault, Storage Account, PostgreSQL
  Flexible Server, the backend App Service, the frontend Static Web App,
  cost guardrails, and (non-prod only) the auto-shutdown Automation Account.
- `infra/azure/modules/*.bicep` — one module per Azure resource.
- `infra/azure/envs/{nonprod,prod}.bicepparam` — per-environment parameters,
  including a budget cap set 25% above the estimated cost. Secrets (e.g. the
  PostgreSQL admin password) are never written to parameter files — they are
  supplied at deploy time via `--parameters` or an Azure DevOps secret
  variable/Key Vault-linked variable group.

## Azure DevOps CI/CD pipeline

`generate` also writes `azure-pipelines.yml` plus `pipelines/templates/*.yml`
implementing:

1. **Build & test** — backend (`manage.py test`) and frontend (`npm test`,
   `npm run build`) in parallel jobs.
2. **Security scan** — `bandit` (Python), `npm audit` (frontend deps), and
   the repo's own `code_review_agent.py` as an AI code-review CI gate.
3. **Infra plan** — `az deployment group what-if` for both environments.
4. **Cost gate** — runs `devops_agent.py plan --fail-over-budget` for each
   environment; fails the pipeline if projected spend exceeds the configured
   budget cap.
5. **Deploy non-prod** — automatic, once the cost gate passes.
6. **Deploy prod** — an Azure DevOps `environment` deployment job
   (`coaching-platform-prod`). Configure a manual-approval check on that
   environment in Azure DevOps (*Pipelines → Environments → approvals and
   checks*) so a human signs off before prod changes apply.

## Cost-management guardrails

- **Azure Budget** (`Microsoft.Consumption/budgets`) per environment, alerting
  at 50%/80% actual and 100% forecasted spend, routed through an **Action
  Group** to an email address (set `costAlertEmail` in the `.bicepparam`
  file or via pipeline variable).
- **Non-prod auto-shutdown** — an Azure Automation Account + runbook +
  nightly schedule stops the backend Web App and PostgreSQL Flexible Server
  outside business hours.
- **`spin-down` / `spin-up` CLI commands** — stop/start the same resources
  on demand without deleting anything (data is preserved).
- **`teardown`** — permanently deletes an environment's resource group
  (`az group delete`). Requires `--confirm <environment>` to match the
  target environment name, on top of `--execute`, before anything runs.
- Every generated resource is tagged (`application`, `environment`,
  `managedBy: devops-agent`) for cost attribution/reporting.

## Usage

```bash
# See what the agent detects about the app (no side effects)
python agents/devops_agent.py analyze

# Show the plan + cost estimate for both environments (writes a report, builds nothing)
python agents/devops_agent.py plan

# Same, but fail (exit 1) if an environment's estimate exceeds its budget cap
python agents/devops_agent.py plan --environment prod --fail-over-budget --budget-cap-usd 200

# Write the Bicep IaC + Azure DevOps pipeline files into the repo
python agents/devops_agent.py generate

# Record explicit approval of the current plan for an environment
python agents/devops_agent.py approve --environment nonprod

# Build (create/update) an approved environment (dry-run by default; add --execute to actually run az)
python agents/devops_agent.py build --environment nonprod --execute

# Stop compute/DB without deleting data
python agents/devops_agent.py spin-down --environment nonprod --execute

# Start it back up
python agents/devops_agent.py spin-up --environment nonprod --execute

# Permanently delete an environment (requires --confirm matching the environment name)
python agents/devops_agent.py teardown --environment nonprod --confirm nonprod --execute
```

## Files this agent owns

- `agents/devops_agent.py` — the agent itself.
- `infra/azure/**` — generated Bicep IaC (commit to git).
- `azure-pipelines.yml`, `pipelines/templates/**` — generated Azure DevOps
  pipeline (commit to git).
- `generated/devops-agent-report.md` — latest plan + cost report.
- `generated/devops-agent-state.json` — recorded approvals (per environment
  plan hash + timestamp).

## Tests

`tests/test_devops_agent.py` covers application analysis, cost/SKU sizing
rules, plan-hash stability and drift detection, the approval gate (blocked
before approval, allowed after, re-blocked on drift), Bicep/pipeline file
generation, lifecycle command construction, and the CLI's exit codes.

## Known limitations

- The generated `main.bicep` always wires the `staticWebApp` module for the
  frontend, and only wires a frontend App Service when the plan lists one.
  A server-rendered (e.g. Next.js) frontend is priced correctly by
  `InfrastructurePlanner`, but its App Service module is not yet included in
  `main.bicep` — only the current app's static Vite/React build is fully
  wired end-to-end. Extend `BicepGenerator`/`main.bicep` if/when an SSR
  frontend is introduced.

