from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from .backend_developer_agent import BackendBuildResult, BackendDeveloperAgent, ParsedRequirements
    from .frontend_developer_agent import BuildResult, FrontendDeveloperAgent, ParsedRequirements as FrontendParsedRequirements
except ImportError:
    from backend_developer_agent import BackendBuildResult, BackendDeveloperAgent, ParsedRequirements
    from frontend_developer_agent import BuildResult, FrontendDeveloperAgent, ParsedRequirements as FrontendParsedRequirements


@dataclass(frozen=True)
class DeveloperBuildResult:
    output_dir: str
    backend: BackendBuildResult
    frontend: BuildResult
    generated_files: list[str]
    report_path: str

    def to_dict(self) -> dict[str, object]:
        return {
            "output_dir": self.output_dir,
            "backend": self.backend.to_dict(),
            "frontend": self.frontend.to_dict(),
            "generated_files": self.generated_files,
            "report_path": self.report_path,
        }


class DeveloperAgent:
    """Single end-to-end developer agent that generates backend and frontend implementations from one requirements document."""

    VERSION = "1.2.0"
    REPORT_FILENAME = "developer-agent-report.md"

    def __init__(self) -> None:
        self.backend_agent = BackendDeveloperAgent()
        self.frontend_agent = FrontendDeveloperAgent()

    def parse_requirements_markdown(self, markdown: str) -> ParsedRequirements:
        return self.backend_agent.parse_requirements_markdown(markdown)

    def build_from_requirements(
        self,
        requirements: ParsedRequirements,
        output_dir: str | Path,
        project_name: str,
        base_url: str = "http://localhost:8000",
        backend_dir_name: str = "backend-app",
        frontend_dir_name: str = "frontend-app",
        backend_project_name: str | None = None,
        frontend_project_name: str | None = None,
    ) -> DeveloperBuildResult:
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)

        backend_dir = root / backend_dir_name
        frontend_dir = root / frontend_dir_name
        backend_name = backend_project_name or f"{project_name}-backend"
        frontend_name = frontend_project_name or f"{project_name}-frontend"

        backend_result = self.backend_agent.build_from_requirements(
            requirements=requirements,
            output_dir=backend_dir,
            project_name=backend_name,
            base_url=base_url,
        )

        frontend_requirements = FrontendParsedRequirements(
            title=requirements.title,
            summary=requirements.summary,
            user_stories=requirements.user_stories,
            functional_requirements=requirements.functional_requirements,
            non_functional_requirements=requirements.non_functional_requirements,
            constraints=requirements.constraints,
        )
        frontend_result = self.frontend_agent.build_from_requirements(
            requirements=frontend_requirements,
            output_dir=frontend_dir,
            project_name=frontend_name,
        )

        generated_files = list(backend_result.generated_files) + list(frontend_result.generated_files)

        report_path = root / self.REPORT_FILENAME
        report_path.write_text(
            self._build_report(
                requirements=requirements,
                backend_result=backend_result,
                frontend_result=frontend_result,
            ),
            encoding="utf-8",
        )
        generated_files.append(str(report_path))

        return DeveloperBuildResult(
            output_dir=str(root),
            backend=backend_result,
            frontend=frontend_result,
            generated_files=generated_files,
            report_path=str(report_path),
        )

    def self_documentation_markdown(self) -> str:
        return "\n".join(
            [
                "# Developer Agent",
                "",
                "## Purpose",
                "",
                "`agents/developer_agent.py` is a single end-to-end developer agent that reads requirements markdown",
                "and generates both backend and frontend implementations in one run.",
                "",
                "## What it does",
                "",
                "- Parses requirements markdown once",
                "- Builds backend implementation and integration contract",
                "- Builds frontend implementation scaffold",
                "- Writes a unified run report",
                "- Applies persistence-ready backend/frontend scaffold alignment for tasks and discussions",
                "",
                "## Usage",
                "",
                "```bash",
                "python agents/developer_agent.py \\",
                "  --requirements-file docs/coaching-platform-requirements.md \\",
                "  --output generated \\",
                "  --backend-dir-name backend-app \\",
                "  --frontend-dir-name frontend-app",
                "```",
                "",
                "## Options",
                "",
                "| Flag | Default | Description |",
                "|---|---|---|",
                "| `--requirements-file` | required | Path to the requirements markdown file |",
                "| `--output` | `generated` | Output root for generated artifacts |",
                "| `--project-name` | `coaching` | Legacy prefix used when backend/frontend project names are not provided |",
                "| `--backend-dir-name` | `backend-app` | Subdirectory name for backend output |",
                "| `--frontend-dir-name` | `frontend-app` | Subdirectory name for frontend output |",
                "| `--backend-project-name` | `coaching-backend` | Backend project name used in generated configs |",
                "| `--frontend-project-name` | `coaching-frontend` | Frontend package/project name |",
                "| `--base-url` | `http://localhost:8000` | Backend base URL written to integration contract |",
                "| `--update-docs` | flag | Regenerate docs/developer-agent.md |",
                "",
                "## Notes",
                "",
                "- Uses Python standard library only.",
                "- Delegates backend and frontend generation to the existing implementation modules.",
                "- By default it updates `generated/backend-app` and `generated/frontend-app` in place.",
                "- Emits aligned scaffolds so planning board actions and discussions can be persisted end to end.",
                f"- Agent version: {self.VERSION}",
                "",
            ]
        )

    def _build_report(
        self,
        requirements: ParsedRequirements,
        backend_result: BackendBuildResult,
        frontend_result: BuildResult,
    ) -> str:
        lines = [
            "# Developer Agent Run Report",
            "",
            f"- Agent version: {self.VERSION}",
            f"- Requirement title: {requirements.title}",
            f"- Backend technology: {backend_result.technology.name} ({backend_result.technology.key})",
            f"- Frontend technology: {frontend_result.technology.name} ({frontend_result.technology.key})",
            "",
            "## Output",
            "",
            f"- Backend output: {backend_result.output_dir}",
            f"- Frontend output: {frontend_result.output_dir}",
            f"- Backend report: {backend_result.report_path}",
            f"- Frontend report: {frontend_result.report_path}",
            "",
            "## Integration contract",
            "",
            f"- Base URL: {backend_result.integration.base_url}",
            f"- API style: {backend_result.integration.api_style}",
            f"- Endpoint count: {len(backend_result.integration.endpoints)}",
            "",
        ]
        return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate backend and frontend implementations from a requirements markdown file."
    )
    parser.add_argument("--requirements-file", required=True, help="Path to requirements markdown.")
    parser.add_argument("--output", default="generated", help="Output root for generated project folders.")
    parser.add_argument(
        "--project-name",
        default="coaching",
        help="Legacy project prefix used when project-name overrides are not provided.",
    )
    parser.add_argument(
        "--backend-dir-name",
        default="backend-app",
        help="Subdirectory created inside --output for backend implementation.",
    )
    parser.add_argument(
        "--frontend-dir-name",
        default="frontend-app",
        help="Subdirectory created inside --output for frontend implementation.",
    )
    parser.add_argument(
        "--backend-project-name",
        default="coaching-backend",
        help="Backend project name used by backend generator.",
    )
    parser.add_argument(
        "--frontend-project-name",
        default="coaching-frontend",
        help="Frontend project/package name used by frontend generator.",
    )
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL for integration contract.")
    parser.add_argument("--update-docs", action="store_true", help="Regenerate docs/developer-agent.md.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    requirements_text = Path(args.requirements_file).read_text(encoding="utf-8")

    agent = DeveloperAgent()
    requirements = agent.parse_requirements_markdown(requirements_text)
    result = agent.build_from_requirements(
        requirements=requirements,
        output_dir=args.output,
        project_name=args.project_name,
        base_url=args.base_url,
        backend_dir_name=args.backend_dir_name,
        frontend_dir_name=args.frontend_dir_name,
        backend_project_name=args.backend_project_name,
        frontend_project_name=args.frontend_project_name,
    )

    if args.update_docs:
        docs_path = Path("docs") / "developer-agent.md"
        docs_path.parent.mkdir(parents=True, exist_ok=True)
        docs_path.write_text(agent.self_documentation_markdown(), encoding="utf-8")
        print(f"Docs updated: {docs_path}", file=sys.stderr)

    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
