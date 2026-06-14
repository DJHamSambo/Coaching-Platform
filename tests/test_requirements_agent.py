from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.requirements_agent import RequirementsAgent


class RequirementsAgentTests(unittest.TestCase):
    def test_distills_text_file_and_url_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            notes_path = Path(temp_dir) / "notes.txt"
            notes_path.write_text(
                "The platform should support reminder messages. "
                "Use Python for the implementation. "
                "What authentication provider should be used?",
                encoding="utf-8",
            )

            agent = RequirementsAgent()
            with patch.object(agent, "fetch_url_text", return_value="The system must generate weekly reports."):
                result = agent.distill(
                    texts=["Build a coaching platform that must manage bookings."],
                    file_paths=[notes_path],
                    urls=["https://example.com/spec"],
                    title="Agent Ready Requirements",
                )

        markdown = result.to_markdown()
        self.assertEqual(result.title, "Agent Ready Requirements")
        self.assertIn("As a user, I want to manage bookings.", result.user_stories)
        self.assertIn("The system shall manage bookings.", result.functional_requirements)
        self.assertIn("The system shall generate weekly reports.", result.functional_requirements)
        self.assertIn("Use Python for the implementation.", result.constraints)
        self.assertIn("What authentication provider should be used?", result.open_questions)
        self.assertIn("## User stories", markdown)
        self.assertIn("## Functional requirements", markdown)
        self.assertIn("- url: https://example.com/spec", markdown)

    def test_requires_at_least_one_source(self) -> None:
        with self.assertRaises(ValueError):
            RequirementsAgent().distill()

    def test_rejects_local_urls(self) -> None:
        with self.assertRaises(ValueError):
            RequirementsAgent().fetch_url_text("http://127.0.0.1/spec")

    def test_distills_coaching_plan_input_into_coherent_outputs(self) -> None:
        text = (
            "As a coach I want to be able to create one to many coaching plans for a coachee. "
            "These should show as a list in target date order. "
            "Each coaching plan should be able to have a title, a description, a status (to do, in progress, done) and one to many actions. "
            "Each of the actions should be able to have a title, description, state (to do, in progress, done) as well as discussion where the coachee can @ a coach. "
            "Actions for all in progress coaching plans should be visualised on a Kanban board with columns for the status, allowing the coachee to drag and drop actions between columns which should also update the status of the action."
        )

        result = RequirementsAgent().distill(texts=[text], title="Coaching Plan Requirements")

        joined_stories = "\n".join(result.user_stories).lower()
        joined_functional = "\n".join(result.functional_requirements).lower()

        self.assertIn("as a coach, i want to create one to many coaching plans", joined_stories)
        self.assertIn("as a coach, i want coaching plans to be shown as a list in target date order", joined_stories)
        self.assertNotIn("as a user, i want to as a coach", joined_stories)

        self.assertIn("the system shall allow coaches to create one to many coaching plans", joined_functional)
        self.assertIn("the system shall show coaching plans as a list in target date order", joined_functional)
        self.assertNotIn("the system shall as a coach", joined_functional)


if __name__ == "__main__":
    unittest.main()
