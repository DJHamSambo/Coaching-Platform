from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agents.devops_agent import (
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


if __name__ == "__main__":
    unittest.main()
