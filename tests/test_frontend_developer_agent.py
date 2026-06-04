from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents.frontend_developer_agent import FrontendDeveloperAgent


class FrontendDeveloperAgentTests(unittest.TestCase):
    def test_chooses_react_vite_for_interactive_workflows(self) -> None:
        markdown = """# Product Requirements

## Functional requirements
- The system shall provide a kanban board for coaching tasks.
- The system shall support task comments and notifications.
"""
        agent = FrontendDeveloperAgent()
        requirements = agent.parse_requirements_markdown(markdown)

        decision = agent.choose_frontend_technology(requirements)

        self.assertEqual(decision.key, "react-vite-ts")

    def test_build_generates_project_and_report(self) -> None:
        markdown = """# Coaching Platform Requirements

## User stories
- As a coachee, I want to manage my coaching tasks.

## Functional requirements
- The system shall support comments and @mentions.
"""
        agent = FrontendDeveloperAgent()
        requirements = agent.parse_requirements_markdown(markdown)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = agent.build_from_requirements(
                requirements=requirements,
                output_dir=temp_dir,
                project_name="coaching-frontend",
            )

            self.assertTrue((Path(temp_dir) / "package.json").exists())
            self.assertTrue((Path(temp_dir) / "README.md").exists())
            self.assertTrue((Path(temp_dir) / "frontend-agent-report.md").exists())
            self.assertTrue((Path(temp_dir) / "src" / "components" / "KanbanBoard.tsx").exists())
            self.assertTrue((Path(temp_dir) / "src" / "components" / "SessionPlanner.tsx").exists())
            self.assertTrue((Path(temp_dir) / "src" / "components" / "DiscussionPanel.tsx").exists())
            self.assertTrue((Path(temp_dir) / "src" / "components" / "InsightsJournal.tsx").exists())
            self.assertTrue((Path(temp_dir) / "src" / "components" / "ResourceLibrary.tsx").exists())
            self.assertIn("frontend-agent-report.md", result.report_path)
            self.assertGreater(len(result.generated_files), 10)

    def test_self_documentation_mentions_current_version(self) -> None:
        agent = FrontendDeveloperAgent()

        doc = agent.self_documentation_markdown()

        self.assertIn("Frontend Developer Agent", doc)
        self.assertIn(agent.VERSION, doc)


if __name__ == "__main__":
    unittest.main()
