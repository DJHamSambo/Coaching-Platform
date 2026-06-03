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


if __name__ == "__main__":
    unittest.main()
