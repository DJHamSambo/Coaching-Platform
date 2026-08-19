from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from agents.devops_agent import (
    AdoApiError,
    AdoProvisionPlan,
    AdoProvisioner,
    ApprovalRequiredError,
    ApprovalState,
    AppAnalyzer,
    AzurePipelineGenerator,
    BicepGenerator,
    DevOpsAgent,
    InfrastructurePlanner,
    LifecycleCommandBuilder,
    main,
)


def _write_backend_and_frontend(repo_root: Path) -> None:
    backend_dir = repo_root / "generated" / "backend-app"
    backend_dir.mkdir(parents=True, exist_ok=True)
    (backend_dir / "manage.py").write_text("# manage.py", encoding="utf-8")
    (backend_dir / "requirements.txt").write_text("django>=5.0\npsycopg2-binary>=2.9\n", encoding="utf-8")

    frontend_dir = repo_root / "generated" / "frontend-app"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    (frontend_dir / "package.json").write_text(
        json.dumps({"dependencies": {"react": "^18.0.0", "vite": "^5.0.0"}}), encoding="utf-8"
    )
    (frontend_dir / "tsconfig.json").write_text("{}", encoding="utf-8")


class AppAnalyzerTests(unittest.TestCase):
    def test_detects_django_backend_and_vite_react_frontend(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _write_backend_and_frontend(repo_root)

            profile = AppAnalyzer().analyze(repo_root)

            self.assertTrue(profile.has_backend)
            self.assertTrue(profile.has_frontend)
            self.assertTrue(profile.needs_database)
            backend = next(c for c in profile.components if c.kind == "backend")
            frontend = next(c for c in profile.components if c.kind == "frontend")
            self.assertEqual(backend.framework, "django")
            self.assertEqual(backend.database_engine, "postgresql")
            self.assertEqual(frontend.framework, "vite+react")
            self.assertTrue(frontend.is_static_build)

    def test_no_components_detected_in_empty_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile = AppAnalyzer().analyze(Path(temp_dir))
            self.assertFalse(profile.has_backend)
            self.assertFalse(profile.has_frontend)
            self.assertEqual(profile.components, [])


class InfrastructurePlannerTests(unittest.TestCase):
    def _profile(self, repo_root: Path):
        _write_backend_and_frontend(repo_root)
        return AppAnalyzer().analyze(repo_root)

    def test_nonprod_is_cheaper_than_prod(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile = self._profile(Path(temp_dir))
            plan = InfrastructurePlanner(app_name="test-app").build_plan(profile)

            nonprod_cost = plan.environments["nonprod"].total_monthly_cost_usd
            prod_cost = plan.environments["prod"].total_monthly_cost_usd

            self.assertLess(nonprod_cost, prod_cost)
            self.assertGreaterEqual(nonprod_cost, 0.0)

    def test_nonprod_includes_auto_shutdown_and_prod_does_not(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile = self._profile(Path(temp_dir))
            plan = InfrastructurePlanner().build_plan(profile)

            nonprod_kinds = {r.resource_kind for r in plan.environments["nonprod"].resources}
            prod_kinds = {r.resource_kind for r in plan.environments["prod"].resources}

            self.assertIn("Automation", nonprod_kinds)
            self.assertNotIn("Automation", prod_kinds)

    def test_both_environments_have_budget_and_action_group(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile = self._profile(Path(temp_dir))
            plan = InfrastructurePlanner().build_plan(profile)

            for env in plan.environments.values():
                kinds = {r.resource_kind for r in env.resources}
                self.assertIn("Budget:Consumption", kinds)
                self.assertIn("ActionGroup:Standard", kinds)

    def test_plan_hash_stable_and_changes_with_sku(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile = self._profile(Path(temp_dir))
            plan_a = InfrastructurePlanner().build_plan(profile)
            plan_b = InfrastructurePlanner().build_plan(profile)
            self.assertEqual(plan_a.plan_hash(), plan_b.plan_hash())

            # Mutate one resource's SKU on a fresh plan; hash must change.
            env = plan_b.environments["nonprod"]
            mutated_resources = list(env.resources)
            mutated_resources[0] = mutated_resources[0].__class__(
                **{**mutated_resources[0].to_dict(), "sku": "B1"}
            )
            object.__setattr__(env, "resources", mutated_resources)
            self.assertNotEqual(plan_a.plan_hash(), plan_b.plan_hash())

    def test_to_markdown_includes_cost_table_and_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile = self._profile(Path(temp_dir))
            plan = InfrastructurePlanner().build_plan(profile)
            markdown = plan.to_markdown()

            self.assertIn("## Environment: nonprod", markdown)
            self.assertIn("## Environment: prod", markdown)
            self.assertIn("Plan hash:", markdown)
            self.assertIn("Grand total", markdown)


class ApprovalGateTests(unittest.TestCase):
    def test_build_blocked_without_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _write_backend_and_frontend(repo_root)
            agent = DevOpsAgent(repo_root, app_name="test-app")

            with self.assertRaises(ApprovalRequiredError):
                agent.build("nonprod", execute=False)

    def test_build_allowed_after_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _write_backend_and_frontend(repo_root)
            agent = DevOpsAgent(repo_root, app_name="test-app")
            plan = agent.plan()
            agent.approve(plan, "nonprod")

            commands = agent.build("nonprod", execute=False)
            self.assertTrue(len(commands) > 0)

    def test_approval_invalidated_by_plan_shape_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _write_backend_and_frontend(repo_root)
            agent = DevOpsAgent(repo_root, app_name="test-app")
            plan = agent.plan()
            agent.approve(plan, "nonprod")

            state = ApprovalState.load(agent.state_path)
            state.approve("nonprod", "a-different-hash-simulating-drift")
            state.save(agent.state_path)

            with self.assertRaises(ApprovalRequiredError):
                agent.build("nonprod", execute=False)

    def test_teardown_cli_requires_matching_confirm_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _write_backend_and_frontend(repo_root)
            exit_code = main(["--repo", str(repo_root), "teardown", "--environment", "prod", "--confirm", "nonprod"])
            self.assertEqual(exit_code, 2)


class BicepGeneratorTests(unittest.TestCase):
    def test_writes_main_and_module_and_param_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _write_backend_and_frontend(repo_root)
            profile = AppAnalyzer().analyze(repo_root)
            plan = InfrastructurePlanner(app_name="test-app").build_plan(profile)

            output_dir = repo_root / "infra" / "azure"
            written = BicepGenerator().write(plan, output_dir)

            self.assertTrue((output_dir / "main.bicep").exists())
            self.assertTrue((output_dir / "modules" / "postgresFlexibleServer.bicep").exists())
            self.assertTrue((output_dir / "modules" / "costGuardrails.bicep").exists())
            self.assertTrue((output_dir / "modules" / "autoShutdown.bicep").exists())
            self.assertTrue((output_dir / "envs" / "nonprod.bicepparam").exists())
            self.assertTrue((output_dir / "envs" / "prod.bicepparam").exists())
            self.assertEqual(len(written), len(set(written)))

    def test_param_file_does_not_contain_secret_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _write_backend_and_frontend(repo_root)
            profile = AppAnalyzer().analyze(repo_root)
            plan = InfrastructurePlanner(app_name="test-app").build_plan(profile)
            output_dir = repo_root / "infra" / "azure"
            BicepGenerator().write(plan, output_dir)

            param_content = (output_dir / "envs" / "nonprod.bicepparam").read_text(encoding="utf-8")
            self.assertNotIn("postgresAdminPassword =", param_content)


class AzurePipelineGeneratorTests(unittest.TestCase):
    def test_writes_pipeline_and_templates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _write_backend_and_frontend(repo_root)
            profile = AppAnalyzer().analyze(repo_root)
            plan = InfrastructurePlanner(app_name="test-app").build_plan(profile)

            pipelines_dir = repo_root / "pipelines"
            AzurePipelineGenerator().write(plan, pipelines_dir)

            self.assertTrue((repo_root / "azure-pipelines.yml").exists())
            self.assertTrue((pipelines_dir / "templates" / "deploy.yml").exists())
            self.assertTrue((pipelines_dir / "templates" / "cost-gate.yml").exists())

            pipeline_text = (repo_root / "azure-pipelines.yml").read_text(encoding="utf-8")
            self.assertIn("coaching-platform-prod", pipeline_text)
            self.assertIn("CostGate", pipeline_text)

    def test_pipeline_template_references_match_actual_write_location(self) -> None:
        # azure-pipelines.yml is written to the repo root while its templates are
        # written under <pipelines_dir>/templates/, so every `template:` reference
        # must be relative to the repo root (i.e. prefixed with the pipelines dir
        # name), not relative to azure-pipelines.yml's own directory.
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _write_backend_and_frontend(repo_root)
            profile = AppAnalyzer().analyze(repo_root)
            plan = InfrastructurePlanner(app_name="test-app").build_plan(profile)

            pipelines_dir = repo_root / "pipelines"
            AzurePipelineGenerator().write(plan, pipelines_dir)

            pipeline_text = (repo_root / "azure-pipelines.yml").read_text(encoding="utf-8")
            template_refs = re.findall(r"template:\s*(\S+\.yml)", pipeline_text)
            self.assertTrue(template_refs, "expected at least one template: reference")
            for ref in template_refs:
                self.assertTrue(
                    (repo_root / ref).exists(),
                    f"template reference '{ref}' does not resolve to a file relative to repo root",
                )

    def test_deploy_template_is_only_referenced_inside_a_deployment_jobs_steps_block(self) -> None:
        # pipelines/templates/deploy.yml is a *steps* template (top-level `parameters:` +
        # `steps:`), so it can only be included under a job's `steps:` list. Referencing
        # it directly as an entry of a stage's `jobs:` list (i.e. as if it were a jobs
        # template) fails Azure Pipelines schema validation ("Unexpected value").
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _write_backend_and_frontend(repo_root)
            profile = AppAnalyzer().analyze(repo_root)
            plan = InfrastructurePlanner(app_name="test-app").build_plan(profile)

            pipelines_dir = repo_root / "pipelines"
            AzurePipelineGenerator().write(plan, pipelines_dir)

            pipeline_text = (repo_root / "azure-pipelines.yml").read_text(encoding="utf-8")
            deploy_template_path = (pipelines_dir.relative_to(repo_root) / "templates" / "deploy.yml").as_posix()

            for match in re.finditer(rf"^(?P<indent> *)- template: {re.escape(deploy_template_path)}", pipeline_text, re.MULTILINE):
                preceding_text = pipeline_text[: match.start()]
                preceding_lines = preceding_text.splitlines()
                nearest_key_line = next(
                    line for line in reversed(preceding_lines) if line.strip().endswith(":")
                )
                self.assertIn(
                    "steps:",
                    nearest_key_line,
                    f"'{deploy_template_path}' must only be referenced under a 'steps:' list, "
                    f"found under '{nearest_key_line.strip()}' instead",
                )


class LifecycleCommandBuilderTests(unittest.TestCase):
    def _plan(self, repo_root: Path):
        _write_backend_and_frontend(repo_root)
        profile = AppAnalyzer().analyze(repo_root)
        return InfrastructurePlanner(app_name="test-app").build_plan(profile)

    def test_teardown_command_targets_correct_resource_group(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            plan = self._plan(repo_root)
            commands = LifecycleCommandBuilder().teardown_commands(plan, "prod")
            self.assertEqual(len(commands), 1)
            self.assertIn("rg-test-app-prod", commands[0].argv)
            self.assertIn("--yes", commands[0].argv)

    def test_spin_down_and_spin_up_target_webapp_and_postgres(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            plan = self._plan(repo_root)
            down_commands = LifecycleCommandBuilder().spin_down_commands(plan, "nonprod")
            up_commands = LifecycleCommandBuilder().spin_up_commands(plan, "nonprod")

            self.assertTrue(any("stop" in c.argv for c in down_commands))
            self.assertTrue(any("start" in c.argv for c in up_commands))
            self.assertTrue(any("webapp" in c.argv for c in down_commands))
            self.assertTrue(any("flexible-server" in c.argv for c in down_commands))


class CLITests(unittest.TestCase):
    def test_plan_command_fails_over_budget_when_cap_too_low(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _write_backend_and_frontend(repo_root)
            exit_code = main([
                "--repo", str(repo_root),
                "plan", "--environment", "prod",
                "--fail-over-budget", "--budget-cap-usd", "1",
            ])
            self.assertEqual(exit_code, 1)

    def test_plan_command_passes_with_generous_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _write_backend_and_frontend(repo_root)
            exit_code = main([
                "--repo", str(repo_root),
                "plan", "--environment", "prod",
                "--fail-over-budget", "--budget-cap-usd", "100000",
            ])
            self.assertEqual(exit_code, 0)

    def test_generate_command_writes_iac_and_pipeline_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _write_backend_and_frontend(repo_root)
            exit_code = main(["--repo", str(repo_root), "generate"])
            self.assertEqual(exit_code, 0)
            self.assertTrue((repo_root / "infra" / "azure" / "main.bicep").exists())
            self.assertTrue((repo_root / "azure-pipelines.yml").exists())

    def test_approve_then_build_dry_run_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _write_backend_and_frontend(repo_root)
            self.assertEqual(main(["--repo", str(repo_root), "approve", "--environment", "nonprod"]), 0)
            self.assertEqual(main(["--repo", str(repo_root), "build", "--environment", "nonprod"]), 0)

    def test_build_without_approval_returns_blocked_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _write_backend_and_frontend(repo_root)
            exit_code = main(["--repo", str(repo_root), "build", "--environment", "nonprod"])
            self.assertEqual(exit_code, 2)

    def test_provision_ado_dry_run_does_not_require_pat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            _write_backend_and_frontend(repo_root)
            exit_code = main([
                "--repo", str(repo_root),
                "provision-ado", "--organization", "myorg", "--project", "MyProject",
            ])
            self.assertEqual(exit_code, 0)


class FakeAdoRestClient:
    """Records calls and returns canned responses keyed by URL substring,
    so AdoProvisioner can be tested without any real network access."""

    def __init__(self) -> None:
        self.organization = "myorg"
        self.calls: list[tuple[str, str, dict | None]] = []
        self.environments: list[dict] = []
        self.checks: list[dict] = []
        self.variable_groups: list[dict] = []
        self._next_environment_id = 1
        self._next_variable_group_id = 100

    def get(self, url: str) -> dict:
        self.calls.append(("GET", url, None))
        if "/_apis/projects/" in url:
            return {"id": "project-id-123"}
        if "/_apis/connectionData" in url:
            return {"authenticatedUser": {"id": "self-user-id"}}
        if "/_apis/identities" in url:
            return {"value": [{"id": "approver-user-id"}]}
        if "/_apis/pipelines/checks/configurations" in url:
            return {"value": [c for c in self.checks if c["resourceId"] in url]}
        if "/_apis/pipelines/environments" in url:
            return {"value": list(self.environments)}
        if "/_apis/distributedtask/variablegroups" in url:
            name = url.split("groupName=")[1].split("&")[0]
            return {"value": [g for g in self.variable_groups if g["name"] == name]}
        raise AssertionError(f"Unexpected GET {url}")

    def post(self, url: str, body: dict) -> dict:
        self.calls.append(("POST", url, body))
        if "/_apis/pipelines/environments" in url:
            env = {"id": str(self._next_environment_id), "name": body["name"]}
            self._next_environment_id += 1
            self.environments.append(env)
            return env
        if "/_apis/pipelines/checks/configurations" in url:
            check = {"type": body["type"], "resourceId": body["resource"]["id"]}
            self.checks.append(check)
            return check
        if "/_apis/distributedtask/variablegroups" in url:
            group = {"id": self._next_variable_group_id, "name": body["name"]}
            self._next_variable_group_id += 1
            self.variable_groups.append(group)
            return group
        raise AssertionError(f"Unexpected POST {url}")


class AdoProvisionerTests(unittest.TestCase):
    def _plan(self, **overrides) -> AdoProvisionPlan:
        defaults = dict(
            organization="myorg",
            project="MyProject",
            nonprod_environment="coaching-platform-nonprod",
            prod_environment="coaching-platform-prod",
            variable_group="coaching-platform-common",
            approver_email=None,
            variables={"AZURE_LOCATION": "uksouth"},
            secret_variable_names=["postgresAdminPassword"],
        )
        defaults.update(overrides)
        return AdoProvisionPlan(**defaults)

    def test_provision_creates_environments_approval_and_variable_group(self) -> None:
        client = FakeAdoRestClient()
        provisioner = AdoProvisioner(client)
        plan = self._plan()

        summary = provisioner.provision(plan, {"postgresAdminPassword": "s3cret!"})

        self.assertTrue(any("coaching-platform-nonprod" in line and "created" in line for line in summary))
        self.assertTrue(any("coaching-platform-prod" in line and "created" in line for line in summary))
        self.assertTrue(any("Approval check" in line and "created" in line for line in summary))
        self.assertTrue(any("coaching-platform-common" in line and "created" in line for line in summary))
        self.assertEqual(len(client.environments), 2)
        self.assertEqual(len(client.checks), 1)
        self.assertEqual(len(client.variable_groups), 1)

    def test_provision_is_idempotent_on_second_run(self) -> None:
        client = FakeAdoRestClient()
        provisioner = AdoProvisioner(client)
        plan = self._plan()

        provisioner.provision(plan, {"postgresAdminPassword": "s3cret!"})
        summary = provisioner.provision(plan, {"postgresAdminPassword": "s3cret!"})

        self.assertTrue(all("already existed" in line for line in summary))
        self.assertEqual(len(client.environments), 2)
        self.assertEqual(len(client.checks), 1)
        self.assertEqual(len(client.variable_groups), 1)

    def test_resolve_approver_id_defaults_to_pat_owner(self) -> None:
        client = FakeAdoRestClient()
        provisioner = AdoProvisioner(client)
        self.assertEqual(provisioner.resolve_approver_id(None), "self-user-id")

    def test_get_authenticated_user_id_uses_preview_api_version(self) -> None:
        # Regression test: connectionData is a preview-only API; a prior bug
        # requested api-version=6.0 without the required "-preview" suffix,
        # which Azure DevOps rejects with HTTP 400
        # (VssInvalidPreviewVersionException).
        client = FakeAdoRestClient()
        provisioner = AdoProvisioner(client)

        provisioner.get_authenticated_user_id()

        get_urls = [url for method, url, _ in client.calls if method == "GET"]
        self.assertEqual(
            get_urls,
            ["https://dev.azure.com/myorg/_apis/connectionData?api-version=7.1-preview.1"],
        )

    def test_resolve_approver_id_looks_up_email(self) -> None:
        client = FakeAdoRestClient()
        provisioner = AdoProvisioner(client)
        self.assertEqual(provisioner.resolve_approver_id("someone@example.com"), "approver-user-id")

    def test_resolve_approver_id_raises_when_not_found(self) -> None:
        client = FakeAdoRestClient()
        client.get = lambda url: {"value": []} if "/_apis/identities" in url else FakeAdoRestClient.get(client, url)
        provisioner = AdoProvisioner(client)
        with self.assertRaises(AdoApiError):
            provisioner.resolve_approver_id("nobody@example.com")

    def test_get_project_id_uses_organization_scoped_url_not_project_scoped(self) -> None:
        # Regression test: "Get a project" is an organization-scoped Azure
        # DevOps REST API (https://dev.azure.com/{org}/_apis/projects/{project}).
        # A prior bug built this from the project-scoped base URL, producing
        # a malformed .../{project}/_apis/projects/{project} path that Azure
        # DevOps rejected with HTTP 401.
        client = FakeAdoRestClient()
        provisioner = AdoProvisioner(client)

        project_id = provisioner.get_project_id("MyProject")

        self.assertEqual(project_id, "project-id-123")
        get_urls = [url for method, url, _ in client.calls if method == "GET"]
        self.assertEqual(get_urls, ["https://dev.azure.com/myorg/_apis/projects/MyProject?api-version=7.1"])

    def test_ensure_variable_group_uses_project_scoped_url(self) -> None:
        # Regression test: Variable Groups is a project-scoped API. A prior
        # bug called it at the organization level, which Azure DevOps
        # rejected with HTTP 400 ("scopeId must not be Guid.Empty") because
        # it couldn't resolve a project GUID from the URL.
        client = FakeAdoRestClient()
        provisioner = AdoProvisioner(client)

        group_id, created = provisioner.ensure_variable_group(
            "MyProject", "project-id-123", "coaching-platform-common", {"AZURE_LOCATION": "uksouth"}, {}
        )

        self.assertTrue(created)
        list_calls = [url for method, url, _ in client.calls if method == "GET"]
        create_calls = [url for method, url, body in client.calls if method == "POST"]
        self.assertEqual(
            list_calls,
            [
                "https://dev.azure.com/myorg/MyProject/_apis/distributedtask/variablegroups"
                "?groupName=coaching-platform-common&api-version=7.1"
            ],
        )
        self.assertEqual(
            create_calls,
            ["https://dev.azure.com/myorg/MyProject/_apis/distributedtask/variablegroups?api-version=7.1"],
        )


if __name__ == "__main__":
    unittest.main()
