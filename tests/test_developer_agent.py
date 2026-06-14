from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agents.developer_agent import DeveloperAgent


REQUIREMENTS_MD = """\
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


class DeveloperAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = DeveloperAgent()
        self.requirements = self.agent.parse_requirements_markdown(REQUIREMENTS_MD)

    def test_build_generates_backend_and_frontend(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.agent.build_from_requirements(
                requirements=self.requirements,
                output_dir=temp_dir,
                project_name="coaching-platform",
            )

            backend_dir = Path(temp_dir) / "backend-app"
            frontend_dir = Path(temp_dir) / "frontend-app"

            self.assertTrue(backend_dir.exists())
            self.assertTrue(frontend_dir.exists())
            self.assertTrue((backend_dir / "backend-integration-contract.json").exists())
            self.assertTrue((frontend_dir / "package.json").exists())
            self.assertTrue((Path(temp_dir) / "developer-agent-report.md").exists())
            self.assertGreater(len(result.generated_files), 20)

    def test_result_is_json_serialisable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.agent.build_from_requirements(
                requirements=self.requirements,
                output_dir=temp_dir,
                project_name="coaching-platform",
            )
            serialised = json.dumps(result.to_dict())
            self.assertIn("backend", serialised)
            self.assertIn("frontend", serialised)

    def test_self_documentation_mentions_end_to_end_role(self) -> None:
        docs = self.agent.self_documentation_markdown()
        self.assertIn("single end-to-end developer agent", docs)
        self.assertIn(self.agent.VERSION, docs)


if __name__ == "__main__":
    unittest.main()
