from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from agents.agentic_developer_agent import (
    AgenticDeveloperAgent,
    AgenticDeveloperAgentError,
    DEFAULT_AGENT_COMMAND,
    REPORT_FILENAME,
)


class FakeRunner:
    """Records the last invocation and returns a configurable result."""

    def __init__(self, returncode: int = 0, stdout: str = "ok", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.calls: list[dict] = []

    def __call__(self, command, **kwargs):  # noqa: D401 - test stub
        self.calls.append({"command": command, "kwargs": kwargs})
        return subprocess.CompletedProcess(
            args=command, returncode=self.returncode, stdout=self.stdout, stderr=self.stderr
        )


class BuildPromptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = AgenticDeveloperAgent(agent_command=DEFAULT_AGENT_COMMAND)

    def test_prompt_includes_task(self) -> None:
        prompt = self.agent.build_prompt("Add a logout button")
        self.assertIn("Add a logout button", prompt)
        self.assertIn("# Coding task", prompt)

    def test_prompt_includes_requirements_and_context(self) -> None:
        prompt = self.agent.build_prompt(
            "Do the thing",
            requirements_text="The system shall do the thing.",
            context_files=["src/app.tsx"],
        )
        self.assertIn("The system shall do the thing.", prompt)
        self.assertIn("src/app.tsx", prompt)

    def test_empty_task_rejected(self) -> None:
        with self.assertRaises(AgenticDeveloperAgentError):
            self.agent.build_prompt("   ")


class BuildCommandTests(unittest.TestCase):
    def test_prompt_file_placeholder_substituted(self) -> None:
        agent = AgenticDeveloperAgent(agent_command="aider --yes --message-file {prompt_file}")
        pf = Path("/tmp/p.md")
        cmd = agent.build_command(pf, Path("/work"), "prompt")
        self.assertEqual(cmd, ["aider", "--yes", "--message-file", str(pf)])

    def test_cwd_placeholder_substituted(self) -> None:
        agent = AgenticDeveloperAgent(agent_command="tool --cwd {cwd} --file {prompt_file}")
        pf = Path("/tmp/p.md")
        work = Path("/work")
        cmd = agent.build_command(pf, work, "prompt")
        self.assertEqual(cmd, ["tool", "--cwd", str(work), "--file", str(pf)])

    def test_prompt_file_appended_when_no_placeholder(self) -> None:
        agent = AgenticDeveloperAgent(agent_command="mytool run")
        pf = Path("/tmp/p.md")
        cmd = agent.build_command(pf, Path("/work"), "prompt")
        self.assertEqual(cmd, ["mytool", "run", str(pf)])

    def test_empty_command_rejected(self) -> None:
        with self.assertRaises(AgenticDeveloperAgentError):
            AgenticDeveloperAgent(agent_command="   ")


class RunTests(unittest.TestCase):
    def test_dry_run_does_not_invoke_runner(self) -> None:
        runner = FakeRunner()
        agent = AgenticDeveloperAgent(agent_command="aider --message-file {prompt_file}", runner=runner)
        with tempfile.TemporaryDirectory() as tmp:
            result = agent.run(task="Refactor X", cwd=tmp, execute=False)
        self.assertTrue(result.dry_run)
        self.assertFalse(result.executed)
        self.assertEqual(runner.calls, [])

    def test_execute_invokes_runner_and_reports_success(self) -> None:
        runner = FakeRunner(returncode=0, stdout="done")
        agent = AgenticDeveloperAgent(agent_command="aider --message-file {prompt_file}", runner=runner)
        with tempfile.TemporaryDirectory() as tmp:
            result = agent.run(task="Refactor X", cwd=tmp, execute=True)
        self.assertTrue(result.executed)
        self.assertTrue(result.succeeded)
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(runner.calls[0]["kwargs"]["cwd"], str(Path(tmp).resolve()))

    def test_execute_nonzero_exit_not_succeeded(self) -> None:
        runner = FakeRunner(returncode=1, stdout="", stderr="boom")
        agent = AgenticDeveloperAgent(agent_command="aider --message-file {prompt_file}", runner=runner)
        with tempfile.TemporaryDirectory() as tmp:
            result = agent.run(task="Refactor X", cwd=tmp, execute=True)
        self.assertTrue(result.executed)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.returncode, 1)

    def test_report_written_to_cwd(self) -> None:
        runner = FakeRunner()
        agent = AgenticDeveloperAgent(agent_command="aider --message-file {prompt_file}", runner=runner)
        with tempfile.TemporaryDirectory() as tmp:
            result = agent.run(task="Refactor X", cwd=tmp, execute=False)
            self.assertTrue((Path(tmp) / REPORT_FILENAME).exists())
            self.assertEqual(result.report_path, str(Path(tmp) / REPORT_FILENAME))

    def test_missing_cwd_rejected(self) -> None:
        agent = AgenticDeveloperAgent(agent_command="aider {prompt_file}")
        with self.assertRaises(AgenticDeveloperAgentError):
            agent.run(task="x", cwd="/path/that/does/not/exist/xyz", execute=False)

    def test_prompt_file_cleaned_up(self) -> None:
        runner = FakeRunner()
        agent = AgenticDeveloperAgent(agent_command="aider --message-file {prompt_file}", runner=runner)
        with tempfile.TemporaryDirectory() as tmp:
            result = agent.run(task="Refactor X", cwd=tmp, execute=True)
        self.assertFalse(Path(result.prompt_file).exists())


if __name__ == "__main__":
    unittest.main()
