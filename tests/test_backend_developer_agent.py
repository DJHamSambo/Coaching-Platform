from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from agents.backend_developer_agent import (
    BackendDeveloperAgent,
    BackendBuildResult,
    IntegrationContract,
    ParsedRequirements,
    TechnologyDecision,
)

COACHING_REQUIREMENTS_MD = """\
# Coaching Platform Requirements

## Summary
- Coaches and coachees need a shared workspace to manage sessions, tasks, and discussions.

## User stories
- As a coach, I want to create and manage coaching sessions with my coachees.
- As a coachee, I want to track my action items and insights from each session.

## Functional requirements
- The system shall provide user registration and authentication via JWT.
- The system shall allow coaches to schedule and update sessions.
- The system shall allow coachees to manage tasks and journal insights.
- The system shall provide a discussion thread per session.
- The system shall support resource sharing between coach and coachee.

## Non-functional requirements
- The API must be secured with JWT authentication.
- The system must be maintainable and well-documented.

## Constraints and assumptions
- Use Python and a REST API.
"""

REALTIME_REQUIREMENTS_MD = """\
# Real-Time Chat Platform Requirements

## Summary
- Users need real-time messaging with WebSocket support.

## Functional requirements
- The system shall provide WebSocket-based real-time chat.
- The system shall support notifications and streaming events.

## Non-functional requirements
- Low latency event delivery.
"""

CONTENT_REQUIREMENTS_MD = """\
# Content Management Platform

## Summary
- Administrators need a user management and content CRUD system.

## Functional requirements
- The system shall provide admin panels for user management.
- The system shall implement role-based permissions.
- The system shall support full CRUD for content objects.
"""


class TestParsedRequirements(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = BackendDeveloperAgent()
        self.reqs = self.agent.parse_requirements_markdown(COACHING_REQUIREMENTS_MD)

    def test_title_is_parsed(self) -> None:
        self.assertEqual(self.reqs.title, "Coaching Platform Requirements")

    def test_summary_is_populated(self) -> None:
        self.assertTrue(len(self.reqs.summary) > 0)

    def test_functional_requirements_are_populated(self) -> None:
        self.assertTrue(len(self.reqs.functional_requirements) > 0)

    def test_all_text_includes_title(self) -> None:
        self.assertIn("coaching platform", self.reqs.all_text)


class TestTechnologySelection(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = BackendDeveloperAgent()

    def test_coaching_requirements_select_fastapi(self) -> None:
        reqs = self.agent.parse_requirements_markdown(COACHING_REQUIREMENTS_MD)
        decision = self.agent.choose_backend_technology(reqs)
        self.assertEqual(decision.key, "fastapi")
        self.assertEqual(decision.language, "python")
        self.assertEqual(decision.framework, "fastapi")

    def test_realtime_requirements_select_node_express(self) -> None:
        reqs = self.agent.parse_requirements_markdown(REALTIME_REQUIREMENTS_MD)
        decision = self.agent.choose_backend_technology(reqs)
        self.assertEqual(decision.key, "node-express-ts")
        self.assertEqual(decision.language, "typescript")

    def test_content_requirements_select_django(self) -> None:
        reqs = self.agent.parse_requirements_markdown(CONTENT_REQUIREMENTS_MD)
        decision = self.agent.choose_backend_technology(reqs)
        self.assertEqual(decision.key, "django-drf")
        self.assertEqual(decision.language, "python")

    def test_decision_has_all_fields(self) -> None:
        reqs = self.agent.parse_requirements_markdown(COACHING_REQUIREMENTS_MD)
        decision = self.agent.choose_backend_technology(reqs)
        self.assertIsInstance(decision.name, str)
        self.assertIsInstance(decision.reason, str)
        self.assertIsInstance(decision.score, int)
        self.assertIsInstance(decision.auth_strategy, str)
        self.assertIsInstance(decision.orm, str)


class TestDomainModuleInference(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = BackendDeveloperAgent()
        self.reqs = self.agent.parse_requirements_markdown(COACHING_REQUIREMENTS_MD)
        self.modules = self.agent.infer_domain_modules(self.reqs)

    def test_users_module_enabled(self) -> None:
        self.assertTrue(self.modules["users"])

    def test_sessions_module_enabled(self) -> None:
        self.assertTrue(self.modules["sessions"])

    def test_tasks_module_enabled(self) -> None:
        self.assertTrue(self.modules["tasks"])

    def test_messages_module_enabled(self) -> None:
        self.assertTrue(self.modules["messages"])

    def test_resources_module_enabled(self) -> None:
        self.assertTrue(self.modules["resources"])


class TestIntegrationContract(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = BackendDeveloperAgent()
        reqs = self.agent.parse_requirements_markdown(COACHING_REQUIREMENTS_MD)
        technology = self.agent.choose_backend_technology(reqs)
        modules = self.agent.infer_domain_modules(reqs)
        self.contract = self.agent.build_integration_contract(technology, modules)

    def test_api_style_is_rest(self) -> None:
        self.assertEqual(self.contract.api_style, "rest")

    def test_cors_origins_included(self) -> None:
        self.assertIn("http://localhost:5173", self.contract.cors_origins)

    def test_openapi_path_set(self) -> None:
        self.assertEqual(self.contract.openapi_path, "/docs")

    def test_endpoints_are_populated(self) -> None:
        self.assertTrue(len(self.contract.endpoints) > 0)

    def test_each_endpoint_has_required_keys(self) -> None:
        for ep in self.contract.endpoints:
            self.assertIn("method", ep)
            self.assertIn("path", ep)
            self.assertIn("description", ep)

    def test_to_dict_is_json_serialisable(self) -> None:
        serialised = json.dumps(self.contract.to_dict())
        self.assertIn("rest", serialised)


class TestFastapiScaffoldGeneration(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = BackendDeveloperAgent()
        self.reqs = self.agent.parse_requirements_markdown(COACHING_REQUIREMENTS_MD)

    def test_fastapi_build_creates_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.agent.build_from_requirements(self.reqs, tmpdir, "test-backend")
            self.assertTrue(Path(result.output_dir).exists())

    def test_fastapi_build_generates_main_py(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.agent.build_from_requirements(self.reqs, tmpdir, "test-backend")
            self.assertTrue(any("main.py" in f for f in result.generated_files))

    def test_fastapi_build_generates_requirements_txt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.agent.build_from_requirements(self.reqs, tmpdir, "test-backend")
            self.assertTrue(any("requirements.txt" in f for f in result.generated_files))

    def test_fastapi_build_generates_integration_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.agent.build_from_requirements(self.reqs, tmpdir, "test-backend")
            contract_file = Path(result.output_dir) / BackendDeveloperAgent.INTEGRATION_CONTRACT_FILENAME
            self.assertTrue(contract_file.exists())
            data = json.loads(contract_file.read_text())
            self.assertIn("endpoints", data)

    def test_fastapi_build_generates_router_for_each_enabled_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.agent.build_from_requirements(self.reqs, tmpdir, "test-backend")
            modules = self.agent.infer_domain_modules(self.reqs)
            for module, enabled in modules.items():
                if enabled:
                    self.assertTrue(
                        any(f"{module}.py" in Path(f).name and "routers" in str(f) for f in result.generated_files),
                        f"Expected router for module '{module}'",
                    )

    def test_fastapi_build_generates_schema_for_each_enabled_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.agent.build_from_requirements(self.reqs, tmpdir, "test-backend")
            modules = self.agent.infer_domain_modules(self.reqs)
            for module, enabled in modules.items():
                if enabled:
                    self.assertTrue(
                        any(f"{module}.py" in Path(f).name and "schemas" in str(f) for f in result.generated_files),
                        f"Expected schema for module '{module}'",
                    )

    def test_fastapi_build_result_is_json_serialisable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.agent.build_from_requirements(self.reqs, tmpdir, "test-backend")
            serialised = json.dumps(result.to_dict())
            self.assertIn("fastapi", serialised)

    def test_fastapi_build_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.agent.build_from_requirements(self.reqs, tmpdir, "test-backend")
            report = Path(result.report_path).read_text()
            self.assertIn("Backend Agent Run Report", report)
            self.assertIn(BackendDeveloperAgent.VERSION, report)


class TestSelfDocumentation(unittest.TestCase):
    def test_self_documentation_contains_version(self) -> None:
        agent = BackendDeveloperAgent()
        docs = agent.self_documentation_markdown()
        self.assertIn(BackendDeveloperAgent.VERSION, docs)

    def test_self_documentation_redirects_to_unified_developer_agent(self) -> None:
        agent = BackendDeveloperAgent()
        docs = agent.self_documentation_markdown()
        self.assertIn("Deprecated", docs)
        self.assertIn("developer_agent.py", docs)

    def test_self_documentation_contains_usage(self) -> None:
        agent = BackendDeveloperAgent()
        docs = agent.self_documentation_markdown()
        self.assertIn("--requirements-file", docs)


if __name__ == "__main__":
    unittest.main()
