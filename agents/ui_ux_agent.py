from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Recommendation:
    rec_id: str
    title: str
    category: str
    priority: str
    effort: str
    rationale: str
    wcag_refs: list[str]
    trend_refs: list[str]
    target_files: list[str]
    approved: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.rec_id,
            "title": self.title,
            "category": self.category,
            "priority": self.priority,
            "effort": self.effort,
            "rationale": self.rationale,
            "wcag_refs": self.wcag_refs,
            "trend_refs": self.trend_refs,
            "target_files": self.target_files,
            "approved": self.approved,
        }


@dataclass(frozen=True)
class ReviewResult:
    reviewed_root: str
    generated_at: str
    score: int
    recommendations: list[Recommendation]
    report_path: str

    def to_dict(self) -> dict[str, object]:
        return {
            "reviewed_root": self.reviewed_root,
            "generated_at": self.generated_at,
            "score": self.score,
            "recommendations": [rec.to_dict() for rec in self.recommendations],
            "report_path": self.report_path,
        }


@dataclass(frozen=True)
class ApprovalResult:
    approved_ids: list[str]
    rejected_ids: list[str]
    handoff_path: str

    def to_dict(self) -> dict[str, object]:
        return {
            "approved_ids": self.approved_ids,
            "rejected_ids": self.rejected_ids,
            "handoff_path": self.handoff_path,
        }


@dataclass(frozen=True)
class ImplementationCheckResult:
    approved_ids: list[str]
    implemented_ids: list[str]
    pending_ids: list[str]
    passed: bool
    report_path: str

    def to_dict(self) -> dict[str, object]:
        return {
            "approved_ids": self.approved_ids,
            "implemented_ids": self.implemented_ids,
            "pending_ids": self.pending_ids,
            "passed": self.passed,
            "report_path": self.report_path,
        }


class UIUXAgent:
    VERSION = "1.1.0"
    REPORT_FILENAME = "ui-ux-agent-report.md"
    APPROVAL_FILENAME = "ui-ux-approved-changes.md"
    IMPLEMENTATION_CHECK_FILENAME = "ui-ux-implementation-check.md"

    def review_frontend(self, frontend_root: str | Path, report_path: str | Path | None = None) -> ReviewResult:
        root = Path(frontend_root)
        if not root.exists():
            raise FileNotFoundError(f"Frontend root not found: {root}")

        files = self._collect_files(root)
        recommendations = self._build_recommendations(root, files)
        score = max(0, 100 - (len(recommendations) * 8))

        output_path = Path(report_path) if report_path else root / self.REPORT_FILENAME
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self._review_markdown(root, score, recommendations), encoding="utf-8")

        return ReviewResult(
            reviewed_root=str(root),
            generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            score=score,
            recommendations=recommendations,
            report_path=str(output_path),
        )

    def approve_recommendations(
        self,
        recommendations: list[Recommendation],
        approved_ids: list[str],
        handoff_path: str | Path,
    ) -> ApprovalResult:
        approved_set = {item.strip() for item in approved_ids if item.strip()}

        approved: list[Recommendation] = []
        rejected: list[str] = []
        for rec in recommendations:
            if rec.rec_id in approved_set:
                approved.append(
                    Recommendation(
                        rec_id=rec.rec_id,
                        title=rec.title,
                        category=rec.category,
                        priority=rec.priority,
                        effort=rec.effort,
                        rationale=rec.rationale,
                        wcag_refs=rec.wcag_refs,
                        trend_refs=rec.trend_refs,
                        target_files=rec.target_files,
                        approved=True,
                    )
                )
            else:
                rejected.append(rec.rec_id)

        out_path = Path(handoff_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(self._handoff_markdown(approved), encoding="utf-8")

        return ApprovalResult(
            approved_ids=[item.rec_id for item in approved],
            rejected_ids=rejected,
            handoff_path=str(out_path),
        )

    def self_documentation_markdown(self) -> str:
        return "\n".join(
            [
                "# UI/UX Agent",
                "",
                "## Purpose",
                "",
                "`agents/ui_ux_agent.py` critically reviews frontend UX quality, current UI trends, and WCAG accessibility coverage.",
                "It outputs recommendations first, and only after approval emits developer-agent handoff instructions.",
                "",
                "## Review focus",
                "",
                "- Visual hierarchy and readability",
                "- Interaction clarity and reduced friction",
                "- Mobile responsiveness and touch targets",
                "- Accessibility heuristics aligned to WCAG 2.2",
                "- Modern frontend UX trends (progressive disclosure, density control, clear feedback states)",
                "",
                "## Workflow",
                "",
                "1. Run review mode to produce recommendations and a score.",
                "2. Approve recommendation IDs.",
                "3. Run approval mode to generate implementation instructions for developer agents.",
                "4. Run enforce mode to verify approved recommendations were implemented.",
                "",
                "## Usage",
                "",
                "```bash",
                "python agents/ui_ux_agent.py review \\",
                "  --frontend-root generated/frontend-app \\",
                "  --report generated/ui-ux-agent-report.md",
                "",
                "python agents/ui_ux_agent.py approve \\",
                "  --recommendations-file generated/ui-ux-recommendations.json \\",
                "  --approved-ids UX-001,UX-003 \\",
                "  --handoff generated/ui-ux-approved-changes.md",
                "",
                "python agents/ui_ux_agent.py enforce \\",
                "  --frontend-root generated/frontend-app \\",
                "  --recommendations-file generated/ui-ux-recommendations.json \\",
                "  --approved-ids UX-001,UX-003 \\",
                "  --verification-report generated/ui-ux-implementation-check.md",
                "```",
                "",
                "## Notes",
                "",
                "- Uses Python standard library only.",
                "- Refreshes this document on each run so the docs stay current with agent behavior.",
                "- Enforce mode exits with a non-zero code if approved UX recommendations are still pending.",
                f"- Agent version: {self.VERSION}",
                "",
            ]
        )

    def verify_approved_implementation(
        self,
        frontend_root: str | Path,
        recommendations: list[Recommendation],
        approved_ids: list[str],
        report_path: str | Path | None = None,
    ) -> ImplementationCheckResult:
        root = Path(frontend_root)
        if not root.exists():
            raise FileNotFoundError(f"Frontend root not found: {root}")

        files = self._collect_files(root)
        approved_set = {item.strip() for item in approved_ids if item.strip()}
        rec_by_id = {rec.rec_id: rec for rec in recommendations}

        implemented: list[str] = []
        pending: list[str] = []
        detail_rows: list[tuple[str, str, list[str]]] = []

        for rec_id in sorted(approved_set):
            rec = rec_by_id.get(rec_id)
            if rec is None:
                pending.append(rec_id)
                detail_rows.append((rec_id, "pending", ["Recommendation id not found in recommendations file."]))
                continue

            ok, evidence = self._is_recommendation_implemented(rec, files)
            if ok:
                implemented.append(rec_id)
                detail_rows.append((rec_id, "implemented", evidence))
            else:
                pending.append(rec_id)
                detail_rows.append((rec_id, "pending", evidence))

        passed = len(pending) == 0
        out_path = Path(report_path) if report_path else root / self.IMPLEMENTATION_CHECK_FILENAME
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            self._implementation_check_markdown(root, approved_ids, implemented, pending, passed, detail_rows),
            encoding="utf-8",
        )

        return ImplementationCheckResult(
            approved_ids=sorted(approved_set),
            implemented_ids=implemented,
            pending_ids=pending,
            passed=passed,
            report_path=str(out_path),
        )

    def _collect_files(self, root: Path) -> dict[str, str]:
        files: dict[str, str] = {}
        include_ext = {".tsx", ".ts", ".css", ".html"}
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in include_ext:
                rel = str(path.relative_to(root)).replace("\\", "/")
                files[rel] = path.read_text(encoding="utf-8")
        return files

    def _build_recommendations(self, root: Path, files: dict[str, str]) -> list[Recommendation]:
        recs: list[Recommendation] = []
        index = 1

        css_text = "\n".join(text for rel, text in files.items() if rel.endswith(".css"))
        html_text = "\n".join(text for rel, text in files.items() if rel.endswith(".html"))
        tsx_text = "\n".join(text for rel, text in files.items() if rel.endswith(".tsx"))

        def next_id() -> str:
            nonlocal index
            rec_id = f"UX-{index:03d}"
            index += 1
            return rec_id

        if "@media" not in css_text:
            recs.append(
                Recommendation(
                    rec_id=next_id(),
                    title="Add responsive breakpoints for mobile-first layouts",
                    category="responsive-design",
                    priority="high",
                    effort="medium",
                    rationale="No responsive media queries were detected. Add breakpoints for mobile, tablet, and desktop to reduce layout friction and improve touch ergonomics.",
                    wcag_refs=["1.4.10 Reflow", "2.5.5 Target Size (Enhanced)"],
                    trend_refs=["mobile-first layout systems", "adaptive density controls"],
                    target_files=self._find_targets(files, ["styles.css", "App.tsx"]),
                )
            )

        if ":focus-visible" not in css_text:
            recs.append(
                Recommendation(
                    rec_id=next_id(),
                    title="Introduce visible focus states across interactive controls",
                    category="accessibility",
                    priority="high",
                    effort="small",
                    rationale="No explicit :focus-visible styling detected. Keyboard users need strong focus indicators to navigate confidently.",
                    wcag_refs=["2.4.7 Focus Visible", "2.1.1 Keyboard"],
                    trend_refs=["inclusive interaction patterns", "high-contrast focus rings"],
                    target_files=self._find_targets(files, ["styles.css"]),
                )
            )

        if "aria-" not in tsx_text and "role=" not in tsx_text:
            recs.append(
                Recommendation(
                    rec_id=next_id(),
                    title="Add semantic landmarks and ARIA support for key workflows",
                    category="accessibility",
                    priority="high",
                    effort="medium",
                    rationale="ARIA attributes and landmark roles are sparse. Add landmarks and labels for navigation regions, dialogs, and dynamic widgets.",
                    wcag_refs=["1.3.1 Info and Relationships", "4.1.2 Name, Role, Value"],
                    trend_refs=["semantic-first component architecture"],
                    target_files=self._find_targets(files, ["App.tsx", "src/components/"] , fallback_contains="components/"),
                )
            )

        if "transition" not in css_text and "animation" not in css_text:
            recs.append(
                Recommendation(
                    rec_id=next_id(),
                    title="Add purposeful motion and reduced-motion support",
                    category="interaction-design",
                    priority="medium",
                    effort="small",
                    rationale="No meaningful motion cues were found. Add restrained transitions for hierarchy and feedback, and include reduced-motion media query support.",
                    wcag_refs=["2.2.2 Pause, Stop, Hide", "2.3.3 Animation from Interactions"],
                    trend_refs=["staggered reveal patterns", "reduced-motion preferences"],
                    target_files=self._find_targets(files, ["styles.css"]),
                )
            )

        has_main = bool(re.search(r"<main[\s>]", html_text + tsx_text, flags=re.IGNORECASE))
        if not has_main:
            recs.append(
                Recommendation(
                    rec_id=next_id(),
                    title="Add a main landmark and skip-to-content pattern",
                    category="accessibility",
                    priority="medium",
                    effort="small",
                    rationale="A dedicated main region and skip navigation were not detected, making keyboard and assistive tech navigation less efficient.",
                    wcag_refs=["2.4.1 Bypass Blocks", "1.3.1 Info and Relationships"],
                    trend_refs=["accessibility-first shells"],
                    target_files=self._find_targets(files, ["index.html", "App.tsx"]),
                )
            )

        if not recs:
            recs.append(
                Recommendation(
                    rec_id=next_id(),
                    title="Maintain UX quality with accessibility regression checks",
                    category="quality-guardrails",
                    priority="low",
                    effort="small",
                    rationale="Core UX and accessibility signals are healthy. Add automated checks (axe + keyboard smoke tests) to preserve standards through future iterations.",
                    wcag_refs=["4.1.3 Status Messages"],
                    trend_refs=["continuous UX quality gates"],
                    target_files=self._find_targets(files, ["src/"] , fallback_contains="src/"),
                )
            )

        return recs

    def _review_markdown(self, root: Path, score: int, recommendations: list[Recommendation]) -> str:
        lines = [
            "# UI/UX Agent Review Report",
            "",
            f"- Generated at: {dt.datetime.now(dt.timezone.utc).isoformat()}",
            f"- Agent version: {self.VERSION}",
            f"- Reviewed root: {root}",
            f"- UX score: {score}/100",
            "",
            "## Recommendations (Review-first)",
            "",
            "Approve recommendation IDs before implementation handoff.",
            "",
        ]
        for rec in recommendations:
            lines.extend(
                [
                    f"### {rec.rec_id} - {rec.title}",
                    f"- Category: {rec.category}",
                    f"- Priority: {rec.priority}",
                    f"- Effort: {rec.effort}",
                    f"- Rationale: {rec.rationale}",
                    f"- WCAG references: {', '.join(rec.wcag_refs)}",
                    f"- Trend references: {', '.join(rec.trend_refs)}",
                    f"- Target files: {', '.join(rec.target_files)}",
                    "",
                ]
            )
        return "\n".join(lines).strip() + "\n"

    def _handoff_markdown(self, approved: list[Recommendation]) -> str:
        lines = [
            "# UI/UX Approved Change Handoff",
            "",
            "This file is generated only after recommendation approval.",
            "",
            "## Developer Agent Instructions",
            "",
        ]

        if not approved:
            lines.extend(
                [
                    "- No approved recommendations were provided.",
                    "- Wait for approved IDs before making UX/UI modifications.",
                    "",
                ]
            )
        else:
            for rec in approved:
                lines.extend(
                    [
                        f"- Apply {rec.rec_id}: {rec.title}",
                        f"  category={rec.category}; priority={rec.priority}; effort={rec.effort}",
                        f"  rationale={rec.rationale}",
                        f"  wcag={', '.join(rec.wcag_refs)}",
                        f"  trends={', '.join(rec.trend_refs)}",
                        f"  targets={', '.join(rec.target_files)}",
                        "  completion=must pass UI/UX enforce mode verification",
                    ]
                )
            lines.append("")

        lines.extend(
            [
                "- Review approved UX recommendations for backend contract impact.",
                "- If a recommendation requires API metadata for accessibility (labels, status semantics, assistive hints), expose the required fields in response payloads and integration contracts.",
                "- Keep endpoint behavior backward compatible unless a breaking change is explicitly approved.",
                "",
                "## Quality Gate",
                "",
                "- Verify each approved change against referenced WCAG criteria.",
                "- Record before/after UX evidence in the next implementation report.",
                "",
            ]
        )
        return "\n".join(lines)

    def _implementation_check_markdown(
        self,
        root: Path,
        approved_ids: list[str],
        implemented: list[str],
        pending: list[str],
        passed: bool,
        detail_rows: list[tuple[str, str, list[str]]],
    ) -> str:
        lines = [
            "# UI/UX Implementation Check",
            "",
            f"- Generated at: {dt.datetime.now(dt.timezone.utc).isoformat()}",
            f"- Agent version: {self.VERSION}",
            f"- Frontend root: {root}",
            f"- Approved IDs: {', '.join(approved_ids) if approved_ids else '(none)'}",
            f"- Result: {'PASS' if passed else 'FAIL'}",
            "",
            "## Status",
            "",
            f"- Implemented: {', '.join(implemented) if implemented else '(none)'}",
            f"- Pending: {', '.join(pending) if pending else '(none)'}",
            "",
            "## Evidence",
            "",
        ]
        for rec_id, status, evidence in detail_rows:
            lines.append(f"### {rec_id} ({status})")
            if evidence:
                lines.extend(f"- {item}" for item in evidence)
            else:
                lines.append("- No evidence provided.")
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _is_recommendation_implemented(self, rec: Recommendation, files: dict[str, str]) -> tuple[bool, list[str]]:
        css_text = "\n".join(text for rel, text in files.items() if rel.endswith(".css"))

        if rec.rec_id == "UX-001":
            has_focus_visible = ":focus-visible" in css_text
            has_visible_indicator = bool(re.search(r"outline|box-shadow|border", css_text, flags=re.IGNORECASE))
            ok = has_focus_visible and has_visible_indicator
            evidence = [
                f"Found :focus-visible selector: {has_focus_visible}",
                f"Found visible indicator rule (outline/box-shadow/border): {has_visible_indicator}",
            ]
            return ok, evidence

        if rec.rec_id == "UX-002":
            has_motion = bool(re.search(r"\b(transition|animation)\b", css_text, flags=re.IGNORECASE))
            has_reduced_motion = "prefers-reduced-motion" in css_text
            ok = has_motion and has_reduced_motion
            evidence = [
                f"Found motion cue (transition/animation): {has_motion}",
                f"Found reduced-motion media query: {has_reduced_motion}",
            ]
            return ok, evidence

        # Generic fallback for future recommendations: if this recommendation no longer appears
        # in a fresh review pass, treat it as implemented.
        fresh = self._build_recommendations(Path("."), files)
        still_flagged = any(item.title.strip().lower() == rec.title.strip().lower() for item in fresh)
        return (not still_flagged), [f"Recommendation still flagged in fresh review: {still_flagged}"]

    @staticmethod
    def _find_targets(files: dict[str, str], patterns: list[str], fallback_contains: str = "") -> list[str]:
        found: list[str] = []
        for rel in files:
            rel_lower = rel.lower()
            if any(pattern.lower() in rel_lower for pattern in patterns):
                found.append(rel)
        if not found and fallback_contains:
            found = [rel for rel in files if fallback_contains.lower() in rel.lower()]
        return found[:6]


def _write_recommendations_json(path: Path, recommendations: list[Recommendation]) -> None:
    payload = [rec.to_dict() for rec in recommendations]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_recommendations_json(path: Path) -> list[Recommendation]:
    data = json.loads(path.read_text(encoding="utf-8"))
    recommendations: list[Recommendation] = []
    for item in data:
        recommendations.append(
            Recommendation(
                rec_id=str(item.get("id", "")),
                title=str(item.get("title", "")),
                category=str(item.get("category", "")),
                priority=str(item.get("priority", "")),
                effort=str(item.get("effort", "")),
                rationale=str(item.get("rationale", "")),
                wcag_refs=[str(ref) for ref in item.get("wcag_refs", [])],
                trend_refs=[str(ref) for ref in item.get("trend_refs", [])],
                target_files=[str(target) for target in item.get("target_files", [])],
                approved=bool(item.get("approved", False)),
            )
        )
    return recommendations


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Critically review frontend UI/UX quality and gate implementation through explicit recommendation approval."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    review = subparsers.add_parser("review", help="Generate UX recommendations first")
    review.add_argument("--frontend-root", required=True, help="Frontend project root to inspect")
    review.add_argument("--report", default="", help="Markdown review report output path")
    review.add_argument(
        "--recommendations-file",
        default="generated/ui-ux-recommendations.json",
        help="JSON output with recommendation IDs used for approval",
    )
    review.add_argument(
        "--self-doc-output",
        default="",
        help="Optional markdown path to refresh this agent documentation",
    )

    approve = subparsers.add_parser("approve", help="Emit implementation handoff from approved IDs")
    approve.add_argument("--recommendations-file", required=True, help="Path to recommendations JSON from review mode")
    approve.add_argument("--approved-ids", required=True, help="Comma-separated recommendation IDs")
    approve.add_argument("--handoff", default="generated/ui-ux-approved-changes.md", help="Handoff markdown output path")
    approve.add_argument(
        "--self-doc-output",
        default="",
        help="Optional markdown path to refresh this agent documentation",
    )

    enforce = subparsers.add_parser("enforce", help="Verify approved recommendations were implemented")
    enforce.add_argument("--frontend-root", required=True, help="Frontend project root to inspect")
    enforce.add_argument("--recommendations-file", required=True, help="Path to recommendations JSON from review mode")
    enforce.add_argument("--approved-ids", required=True, help="Comma-separated recommendation IDs")
    enforce.add_argument(
        "--verification-report",
        default="generated/ui-ux-implementation-check.md",
        help="Markdown output path for implementation verification report",
    )
    enforce.add_argument(
        "--self-doc-output",
        default="",
        help="Optional markdown path to refresh this agent documentation",
    )

    return parser


def main() -> int:
    args = _build_parser().parse_args()
    agent = UIUXAgent()

    default_doc_path = Path(__file__).resolve().parents[1] / "docs" / "ui-ux-agent.md"
    doc_path = Path(getattr(args, "self_doc_output", "") or default_doc_path)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(agent.self_documentation_markdown(), encoding="utf-8")

    if args.mode == "review":
        report_path = Path(args.report) if args.report else None
        result = agent.review_frontend(args.frontend_root, report_path=report_path)
        _write_recommendations_json(Path(args.recommendations_file), result.recommendations)
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    recommendations = _load_recommendations_json(Path(args.recommendations_file))
    approved_ids = [item.strip() for item in args.approved_ids.split(",") if item.strip()]

    if args.mode == "approve":
        result = agent.approve_recommendations(recommendations, approved_ids, args.handoff)
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    result = agent.verify_approved_implementation(
        frontend_root=args.frontend_root,
        recommendations=recommendations,
        approved_ids=approved_ids,
        report_path=args.verification_report,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
