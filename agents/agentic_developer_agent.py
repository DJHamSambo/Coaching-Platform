"""Agentic developer agent (Option D): wrap an external coding-agent CLI.

Unlike :mod:`agents.developer_agent`, which deterministically generates code
from a requirements document using templates, this agent delegates the actual
code-writing to a *real* autonomous coding-agent CLI (for example ``aider`` or
the GitHub Copilot CLI). It builds a well-formed prompt from a natural-language
task (plus optional requirements/context files), then invokes the configured
CLI as a subprocess against the working tree.

Design goals / guardrails
-------------------------
* **Dry-run by default** — the command and prompt are previewed but nothing is
  executed unless ``--execute`` is passed, so it never touches committed code
  until you approve.
* **No shell injection** — the configured command is tokenised with ``shlex``
  and run without ``shell=True``; placeholders are substituted per-token.
* **Scoped working directory** — the target directory must exist; the CLI runs
  with that directory as its CWD.
* **Bounded** — a configurable timeout caps runaway runs.
* **Configurable command** — the wrapped CLI is set via ``--agent-command`` or
  the ``AGENTIC_DEV_AGENT_CMD`` environment variable, so this is not locked to a
  single tool.

The wrapped command may contain the placeholders ``{prompt_file}`` (path to a
temp file containing the full prompt) and/or ``{cwd}``. If neither
``{prompt_file}`` nor ``{prompt}`` appears, the prompt-file path is appended as
the final argument.

Examples of commands to wrap::

    aider --yes --message-file {prompt_file}
    copilot --prompt-file {prompt_file}
    my-coding-agent run --cwd {cwd} --instructions {prompt_file}

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Callable, Sequence


# Default command used when neither --agent-command nor AGENTIC_DEV_AGENT_CMD is
# set. aider is a widely-used autonomous coding CLI that can read a message file
# and apply edits non-interactively with --yes.
DEFAULT_AGENT_COMMAND = "aider --yes --message-file {prompt_file}"

DEFAULT_TIMEOUT_SECONDS = 1800

REPORT_FILENAME = "agentic-developer-report.md"

# A subprocess.run-compatible callable, injected for testability.
Runner = Callable[..., subprocess.CompletedProcess]


@dataclass(frozen=True)
class AgenticRunResult:
    """Outcome of a single agentic run."""

    command: list[str]
    prompt: str
    prompt_file: str
    cwd: str
    dry_run: bool
    executed: bool
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    report_path: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.executed and not self.timed_out and self.returncode == 0

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["succeeded"] = self.succeeded
        return data


class AgenticDeveloperAgentError(RuntimeError):
    """Raised for invalid configuration or inputs."""


class AgenticDeveloperAgent:
    """Wraps an external autonomous coding-agent CLI behind a safe interface."""

    VERSION = "0.1.0"

    def __init__(
        self,
        agent_command: str | None = None,
        runner: Runner | None = None,
    ) -> None:
        self.agent_command = (
            agent_command
            or os.environ.get("AGENTIC_DEV_AGENT_CMD")
            or DEFAULT_AGENT_COMMAND
        ).strip()
        if not self.agent_command:
            raise AgenticDeveloperAgentError("agent command must not be empty")
        self._runner: Runner = runner or subprocess.run

    # -- prompt construction ------------------------------------------------

    def build_prompt(
        self,
        task: str,
        requirements_text: str | None = None,
        context_files: Sequence[str] | None = None,
    ) -> str:
        task = (task or "").strip()
        if not task:
            raise AgenticDeveloperAgentError("task description must not be empty")

        sections: list[str] = [
            "# Coding task",
            "",
            "You are an autonomous coding agent working in an existing repository.",
            "Implement the task below. Make focused, correct changes, run the",
            "project's tests where possible, and avoid touching unrelated code.",
            "",
            "## Task",
            "",
            task,
        ]

        if requirements_text and requirements_text.strip():
            sections += [
                "",
                "## Requirements context",
                "",
                requirements_text.strip(),
            ]

        if context_files:
            listed = "\n".join(f"- {path}" for path in context_files)
            sections += [
                "",
                "## Relevant files",
                "",
                listed,
            ]

        sections += [
            "",
            "## Constraints",
            "",
            "- Keep changes minimal and idiomatic for this codebase.",
            "- Do not modify version control history or delete unrelated files.",
            "- Prefer adding/updating tests for new behaviour.",
            "",
        ]
        return "\n".join(sections)

    # -- command construction ----------------------------------------------

    def build_command(self, prompt_file: Path, cwd: Path, prompt: str) -> list[str]:
        try:
            tokens = shlex.split(self.agent_command)
        except ValueError as exc:
            raise AgenticDeveloperAgentError(
                f"could not parse agent command {self.agent_command!r}: {exc}"
            ) from exc
        if not tokens:
            raise AgenticDeveloperAgentError("agent command produced no tokens")

        substitutions = {
            "{prompt_file}": str(prompt_file),
            "{cwd}": str(cwd),
            "{prompt}": prompt,
        }

        rendered: list[str] = []
        used_prompt_placeholder = False
        for token in tokens:
            new_token = token
            for placeholder, value in substitutions.items():
                if placeholder in new_token:
                    new_token = new_token.replace(placeholder, value)
                    if placeholder in ("{prompt_file}", "{prompt}"):
                        used_prompt_placeholder = True
            rendered.append(new_token)

        if not used_prompt_placeholder:
            rendered.append(str(prompt_file))
        return rendered

    # -- execution ----------------------------------------------------------

    def run(
        self,
        task: str,
        cwd: str | Path = ".",
        requirements_text: str | None = None,
        context_files: Sequence[str] | None = None,
        execute: bool = False,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        write_report: bool = True,
    ) -> AgenticRunResult:
        warnings: list[str] = []

        cwd_path = Path(cwd).resolve()
        if not cwd_path.exists() or not cwd_path.is_dir():
            raise AgenticDeveloperAgentError(f"working directory does not exist: {cwd_path}")

        repo_root = Path(__file__).resolve().parent.parent
        try:
            cwd_path.relative_to(repo_root)
        except ValueError:
            warnings.append(f"working directory {cwd_path} is outside the repo root {repo_root}")

        prompt = self.build_prompt(task, requirements_text, context_files)

        # Persist the prompt to a temp file the wrapped CLI can read.
        fd, tmp_name = tempfile.mkstemp(prefix="agentic-prompt-", suffix=".md", text=True)
        prompt_file = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(prompt)

        try:
            command = self.build_command(prompt_file, cwd_path, prompt)

            if not execute:
                result = AgenticRunResult(
                    command=command,
                    prompt=prompt,
                    prompt_file=str(prompt_file),
                    cwd=str(cwd_path),
                    dry_run=True,
                    executed=False,
                    warnings=warnings,
                )
            else:
                returncode: int | None
                stdout = ""
                stderr = ""
                timed_out = False
                try:
                    completed = self._runner(
                        command,
                        cwd=str(cwd_path),
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                    )
                    returncode = completed.returncode
                    stdout = completed.stdout or ""
                    stderr = completed.stderr or ""
                except FileNotFoundError as exc:
                    raise AgenticDeveloperAgentError(
                        f"agent command not found: {command[0]!r}. Install it or set "
                        f"--agent-command / AGENTIC_DEV_AGENT_CMD."
                    ) from exc
                except subprocess.TimeoutExpired as exc:
                    returncode = None
                    timed_out = True
                    stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
                    stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
                    warnings.append(f"agent timed out after {timeout}s")

                result = AgenticRunResult(
                    command=command,
                    prompt=prompt,
                    prompt_file=str(prompt_file),
                    cwd=str(cwd_path),
                    dry_run=False,
                    executed=True,
                    returncode=returncode,
                    stdout=stdout,
                    stderr=stderr,
                    timed_out=timed_out,
                    warnings=warnings,
                )

            if write_report:
                report_path = cwd_path / REPORT_FILENAME
                report_path.write_text(self._build_report(result), encoding="utf-8")
                result = replace(result, report_path=str(report_path))

            return result
        finally:
            # The prompt file is a temporary artifact; clean it up.
            try:
                prompt_file.unlink(missing_ok=True)
            except OSError:
                pass

    # -- reporting ----------------------------------------------------------

    def _build_report(self, result: AgenticRunResult) -> str:
        status = (
            "dry-run (not executed)"
            if result.dry_run
            else ("timed out" if result.timed_out else f"exit code {result.returncode}")
        )
        lines = [
            "# Agentic Developer Run Report",
            "",
            f"- Agent version: {self.VERSION}",
            f"- Wrapped command: `{self.agent_command}`",
            f"- Status: {status}",
            f"- Working directory: {result.cwd}",
            "",
            "## Resolved command",
            "",
            "```",
            " ".join(shlex.quote(part) for part in result.command),
            "```",
            "",
        ]
        if result.warnings:
            lines += ["## Warnings", ""] + [f"- {w}" for w in result.warnings] + [""]
        if result.executed:
            lines += [
                "## Output (truncated)",
                "",
                "```",
                (result.stdout or "")[-4000:],
                "```",
                "",
            ]
            if result.stderr.strip():
                lines += ["### stderr (truncated)", "", "```", result.stderr[-2000:], "```", ""]
        return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Agentic developer agent: delegate a coding task to an external "
            "autonomous coding-agent CLI (Option D). Dry-run by default."
        )
    )
    task_group = parser.add_mutually_exclusive_group(required=True)
    task_group.add_argument("--task", help="Natural-language task description.")
    task_group.add_argument("--task-file", help="Path to a file containing the task description.")

    parser.add_argument(
        "--requirements-file",
        help="Optional requirements markdown to include as context.",
    )
    parser.add_argument(
        "--context-file",
        action="append",
        default=[],
        dest="context_files",
        help="Relevant file path to hint to the agent (repeatable).",
    )
    parser.add_argument(
        "--cwd",
        default=".",
        help="Working directory the wrapped agent runs in (default: current dir).",
    )
    parser.add_argument(
        "--agent-command",
        default=None,
        help=(
            "Command to invoke the external coding agent. May contain "
            "{prompt_file} and/or {cwd}. Defaults to AGENTIC_DEV_AGENT_CMD or "
            f"'{DEFAULT_AGENT_COMMAND}'."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Seconds before the agent run is aborted (default: {DEFAULT_TIMEOUT_SECONDS}).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually run the agent. Without this flag the run is a dry-run preview.",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Do not write the run report file.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.task_file:
        task = Path(args.task_file).read_text(encoding="utf-8")
    else:
        task = args.task

    requirements_text = None
    if args.requirements_file:
        requirements_text = Path(args.requirements_file).read_text(encoding="utf-8")

    agent = AgenticDeveloperAgent(agent_command=args.agent_command)

    try:
        result = agent.run(
            task=task,
            cwd=args.cwd,
            requirements_text=requirements_text,
            context_files=args.context_files,
            execute=args.execute,
            timeout=args.timeout,
            write_report=not args.no_report,
        )
    except AgenticDeveloperAgentError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2

    print(json.dumps(result.to_dict(), indent=2))
    if result.dry_run:
        print(
            "\nDry-run only. Re-run with --execute to invoke the agent.",
            file=sys.stderr,
        )
        return 0
    return 0 if result.succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
