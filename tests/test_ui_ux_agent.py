from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents.ui_ux_agent import Recommendation, UIUXAgent


class UIUXAgentTests(unittest.TestCase):
    def test_review_generates_recommendations_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "index.html").write_text(
                """<!doctype html>
<html lang='en'>
  <head><meta charset='UTF-8' /></head>
  <body>
    <div id='root'></div>
  </body>
</html>
""",
                encoding="utf-8",
            )
            (root / "src").mkdir(parents=True, exist_ok=True)
            (root / "src" / "App.tsx").write_text(
                """export function App() {
  return <button>Open</button>;
}
""",
                encoding="utf-8",
            )
            (root / "src" / "styles.css").write_text(
                """body { font-family: sans-serif; }
button { border: none; }
""",
                encoding="utf-8",
            )

            result = UIUXAgent().review_frontend(root)

            self.assertTrue((root / "ui-ux-agent-report.md").exists())
            self.assertGreater(len(result.recommendations), 0)
            self.assertTrue(any(rec.wcag_refs for rec in result.recommendations))

    def test_approval_outputs_only_approved_handoff(self) -> None:
        recs = [
            Recommendation(
                rec_id="UX-001",
                title="Add focus states",
                category="accessibility",
                priority="high",
                effort="small",
                rationale="Keyboard navigation confidence",
                wcag_refs=["2.4.7 Focus Visible"],
                trend_refs=["inclusive interaction patterns"],
                target_files=["src/styles.css"],
            ),
            Recommendation(
                rec_id="UX-002",
                title="Add responsive breakpoints",
                category="responsive-design",
                priority="high",
                effort="medium",
                rationale="Improve mobile UX",
                wcag_refs=["1.4.10 Reflow"],
                trend_refs=["mobile-first layout systems"],
                target_files=["src/styles.css"],
            ),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            handoff = Path(temp_dir) / "handoff.md"
            result = UIUXAgent().approve_recommendations(recs, ["UX-001"], handoff)
            content = handoff.read_text(encoding="utf-8")

            self.assertEqual(result.approved_ids, ["UX-001"])
            self.assertIn("Apply UX-001", content)
            self.assertNotIn("Apply UX-002", content)

    def test_self_documentation_mentions_current_version(self) -> None:
        agent = UIUXAgent()

        doc = agent.self_documentation_markdown()

        self.assertIn("UI/UX Agent", doc)
        self.assertIn(agent.VERSION, doc)

    def test_verify_fails_when_approved_items_not_implemented(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "src").mkdir(parents=True, exist_ok=True)
            (root / "src" / "styles.css").write_text("button { border: none; }\n", encoding="utf-8")

            recs = [
                Recommendation(
                    rec_id="UX-001",
                    title="Introduce visible focus states across interactive controls",
                    category="accessibility",
                    priority="high",
                    effort="small",
                    rationale="Keyboard navigation confidence",
                    wcag_refs=["2.4.7 Focus Visible"],
                    trend_refs=["inclusive interaction patterns"],
                    target_files=["src/styles.css"],
                ),
                Recommendation(
                    rec_id="UX-002",
                    title="Add purposeful motion and reduced-motion support",
                    category="interaction-design",
                    priority="medium",
                    effort="small",
                    rationale="Motion + reduced motion",
                    wcag_refs=["2.3.3 Animation from Interactions"],
                    trend_refs=["reduced-motion preferences"],
                    target_files=["src/styles.css"],
                ),
            ]

            result = UIUXAgent().verify_approved_implementation(
                frontend_root=root,
                recommendations=recs,
                approved_ids=["UX-001", "UX-002"],
            )

            self.assertFalse(result.passed)
            self.assertEqual(set(result.pending_ids), {"UX-001", "UX-002"})

    def test_verify_passes_when_approved_items_are_implemented(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "src").mkdir(parents=True, exist_ok=True)
            (root / "src" / "styles.css").write_text(
                """
button { transition: background-color 180ms ease; }
button:focus-visible { outline: 3px solid #0b766e; outline-offset: 2px; }
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
""",
                encoding="utf-8",
            )

            recs = [
                Recommendation(
                    rec_id="UX-001",
                    title="Introduce visible focus states across interactive controls",
                    category="accessibility",
                    priority="high",
                    effort="small",
                    rationale="Keyboard navigation confidence",
                    wcag_refs=["2.4.7 Focus Visible"],
                    trend_refs=["inclusive interaction patterns"],
                    target_files=["src/styles.css"],
                ),
                Recommendation(
                    rec_id="UX-002",
                    title="Add purposeful motion and reduced-motion support",
                    category="interaction-design",
                    priority="medium",
                    effort="small",
                    rationale="Motion + reduced motion",
                    wcag_refs=["2.3.3 Animation from Interactions"],
                    trend_refs=["reduced-motion preferences"],
                    target_files=["src/styles.css"],
                ),
            ]

            result = UIUXAgent().verify_approved_implementation(
                frontend_root=root,
                recommendations=recs,
                approved_ids=["UX-001", "UX-002"],
            )

            self.assertTrue(result.passed)
            self.assertEqual(set(result.implemented_ids), {"UX-001", "UX-002"})


if __name__ == "__main__":
    unittest.main()
