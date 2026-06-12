from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agents.gitflow_agent import AutoImplementResult, CIResult, DryRunPullRequestBackend, GitFlowAgent, PullRequestResult


class GitFlowAgentTests(unittest.TestCase):
    @staticmethod
    def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_process_change_builds_gitflow_plan(self) -> None:
        agent = GitFlowAgent(
            repo_path="/tmp/workspace/DJHamSambo/Coaching-Platform",
            pr_backend=DryRunPullRequestBackend(),
        )

        plan = agent.process_change(
            feature_name="Requirements Agent",
            commit_message="feat: add requirements agent",
            change_summary="Add the requirements agent and supporting docs.",
            execute=False,
        )

        self.assertEqual(plan.feature_branch, "feature/requirements-agent")
        self.assertEqual(plan.commands[0][-2:], ["fetch", "origin"])
        self.assertEqual(plan.commands[1][-1], "main")
        self.assertEqual(plan.feature_pull_request.request.base, "main")
        self.assertEqual(plan.feature_pull_request.mode, "dry-run")
        self.assertIn("feature/requirements-agent", plan.feature_pull_request.request.title.lower())

    def test_process_change_uses_main_as_base_branch(self) -> None:
        agent = GitFlowAgent(
            repo_path="/tmp/workspace/DJHamSambo/Coaching-Platform",
            pr_backend=DryRunPullRequestBackend(),
        )

        plan = agent.process_change(
            feature_name="Main Workflow",
            commit_message="feat: test main workflow",
            change_summary="Ensure main-only workflow.",
            execute=False,
        )

        self.assertEqual(plan.feature_pull_request.request.base, "main")
        self.assertEqual(plan.feature_pull_request.request.head, "feature/main-workflow")

    def test_process_change_falls_back_to_dry_run_prs(self) -> None:
        failing_backend = Mock()
        failing_backend.create_pull_request.side_effect = RuntimeError("network blocked")
        agent = GitFlowAgent(
            repo_path="/tmp/workspace/DJHamSambo/Coaching-Platform",
            pr_backend=failing_backend,
        )

        plan = agent.process_change(
            feature_name="Git Flow Agent",
            commit_message="feat: add git flow agent",
            change_summary="Add a git flow agent.",
        )

        self.assertIsInstance(plan.feature_pull_request, PullRequestResult)
        self.assertEqual(plan.feature_pull_request.mode, "dry-run")

    def test_cleanup_merged_feature_branch_defaults_to_local_and_remote(self) -> None:
        agent = GitFlowAgent(
            repo_path="/tmp/workspace/DJHamSambo/Coaching-Platform",
            pr_backend=DryRunPullRequestBackend(),
        )

        cleanup_plan = agent.cleanup_merged_feature_branch(feature_name="Requirements Agent")

        self.assertEqual(cleanup_plan.feature_branch, "feature/requirements-agent")
        self.assertEqual(cleanup_plan.local_commands[0][-2:], ["-d", "feature/requirements-agent"])
        self.assertEqual(cleanup_plan.remote_commands[0][-3:], ["origin", "--delete", "feature/requirements-agent"])

    def test_cleanup_merged_feature_branch_can_skip_local_or_remote(self) -> None:
        agent = GitFlowAgent(
            repo_path="/tmp/workspace/DJHamSambo/Coaching-Platform",
            pr_backend=DryRunPullRequestBackend(),
        )

        cleanup_plan = agent.cleanup_merged_feature_branch(
            feature_name="Requirements Agent",
            delete_local=False,
            delete_remote=True,
        )

        self.assertEqual(cleanup_plan.local_commands, [])
        self.assertEqual(len(cleanup_plan.remote_commands), 1)

    @patch("agents.gitflow_agent.subprocess.run")
    @patch("agents.gitflow_agent._local_branch_exists", return_value=True)
    @patch.object(GitFlowAgent, "_has_staged_changes", return_value=False)
    def test_process_change_execute_is_idempotent_for_existing_branch_and_empty_commit(
        self,
        _has_changes: Mock,
        _branch_exists: Mock,
        run_mock: Mock,
    ) -> None:
        run_mock.return_value = Mock(returncode=0, stderr="")
        agent = GitFlowAgent(
            repo_path="/tmp/workspace/DJHamSambo/Coaching-Platform",
            pr_backend=DryRunPullRequestBackend(),
        )

        agent.process_change(
            feature_name="Requirements Agent",
            commit_message="feat: add requirements agent",
            change_summary="Add the requirements agent and supporting docs.",
            execute=True,
        )

        all_calls = [" ".join(call.args[0]) for call in run_mock.call_args_list]
        self.assertTrue(any(" checkout feature/requirements-agent" in c for c in all_calls))
        self.assertFalse(any(" checkout -b feature/requirements-agent" in c for c in all_calls))
        self.assertFalse(any(" commit -m " in c for c in all_calls))

    @patch.object(GitFlowAgent, "_run_git")
    @patch("agents.gitflow_agent._remote_branch_exists", return_value=False)
    @patch("agents.gitflow_agent._local_branch_exists", return_value=False)
    def test_cleanup_merged_feature_branch_is_noop_when_feature_branch_missing(
        self,
        _local_exists: Mock,
        _remote_exists: Mock,
        run_git_mock: Mock,
    ) -> None:
        run_git_mock.return_value = Mock(returncode=0, stderr="")
        agent = GitFlowAgent(
            repo_path="/tmp/workspace/DJHamSambo/Coaching-Platform",
            pr_backend=DryRunPullRequestBackend(),
        )

        cleanup_plan = agent.cleanup_merged_feature_branch(
            feature_name="Requirements Agent",
            execute=True,
        )

        self.assertEqual(cleanup_plan.feature_branch, "feature/requirements-agent")
        self.assertEqual(run_git_mock.call_count, 1)

    @patch.object(GitFlowAgent, "run_code_review_ci")
    @patch.object(GitFlowAgent, "_dispatch_developer_fixers", return_value=True)
    @patch.object(GitFlowAgent, "_checkout_feature_branch")
    @patch.object(GitFlowAgent, "_has_staged_changes", return_value=True)
    @patch.object(GitFlowAgent, "_run_git")
    def test_auto_implement_retries_ci_and_commits(
        self,
        run_git_mock: Mock,
        _has_staged: Mock,
        _checkout: Mock,
        _dispatch: Mock,
        run_ci_mock: Mock,
    ) -> None:
        run_git_mock.return_value = Mock(returncode=0, stdout="", stderr="")
        failing_ci = CIResult(
            passed=False,
            score=4.0,
            models_used=["test"],
            critical=0,
            high=1,
            medium=0,
            low=0,
            fix_instructions_path=None,
        )
        passing_ci = CIResult(
            passed=True,
            score=8.0,
            models_used=["test"],
            critical=0,
            high=0,
            medium=0,
            low=1,
            fix_instructions_path=None,
        )
        run_ci_mock.return_value = passing_ci

        agent = GitFlowAgent(
            repo_path="/tmp/workspace/DJHamSambo/Coaching-Platform",
            pr_backend=DryRunPullRequestBackend(),
        )

        result = agent._auto_implement_ci_fixes(
            feature_branch="feature/requirements-agent",
            initial_ci=failing_ci,
            max_attempts=2,
            auto_commit_message="fix: auto-implement code review findings",
        )

        self.assertTrue(result.final_ci.passed)
        self.assertTrue(result.committed)
        self.assertEqual(result.attempts, 1)
        all_calls = [" ".join(call.args[0]) for call in run_git_mock.call_args_list]
        self.assertTrue(any(c.startswith("commit -m ") for c in all_calls))
        self.assertTrue(any(c == "push origin feature/requirements-agent" for c in all_calls))

    @patch.object(GitFlowAgent, "_run_git")
    @patch.object(GitFlowAgent, "_is_ancestor", return_value=True)
    @patch("agents.gitflow_agent._remote_branch_exists", return_value=False)
    @patch("agents.gitflow_agent._local_branch_exists", return_value=False)
    @patch.object(GitFlowAgent, "_auto_implement_ci_fixes")
    @patch.object(GitFlowAgent, "run_code_review_ci")
    def test_merge_feature_into_main_uses_auto_implement_when_enabled(
        self,
        run_ci_mock: Mock,
        auto_impl_mock: Mock,
        _local_exists: Mock,
        _remote_exists: Mock,
        _is_ancestor: Mock,
        run_git_mock: Mock,
    ) -> None:
        run_git_mock.return_value = Mock(returncode=0, stdout="", stderr="")
        failing_ci = CIResult(
            passed=False,
            score=4.0,
            models_used=["test"],
            critical=0,
            high=1,
            medium=0,
            low=0,
            fix_instructions_path=None,
        )
        passing_ci = CIResult(
            passed=True,
            score=8.0,
            models_used=["test"],
            critical=0,
            high=0,
            medium=0,
            low=1,
            fix_instructions_path=None,
        )
        run_ci_mock.return_value = failing_ci
        auto_impl_mock.return_value = AutoImplementResult(attempts=1, committed=True, final_ci=passing_ci)

        agent = GitFlowAgent(
            repo_path="/tmp/workspace/DJHamSambo/Coaching-Platform",
            pr_backend=DryRunPullRequestBackend(),
        )

        plan = agent.merge_feature_into_main(
            feature_name="Requirements Agent",
            execute=True,
            auto_implement=True,
            max_auto_attempts=2,
        )

        self.assertIsNotNone(plan.auto_implement)
        auto_impl_mock.assert_called_once()

    def test_end_to_end_main_flow_process_merge_and_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            remote = tmp_path / "remote.git"
            repo = tmp_path / "repo"

            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True, text=True)

            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            self._git(repo, "config", "user.name", "GitFlow Test")
            self._git(repo, "config", "user.email", "gitflow-test@example.com")
            self._git(repo, "branch", "-M", "main")
            self._git(repo, "remote", "add", "origin", str(remote))

            (repo / "README.md").write_text("# integration test\n", encoding="utf-8")
            self._git(repo, "add", "README.md")
            self._git(repo, "commit", "-m", "chore: initial commit")
            self._git(repo, "push", "-u", "origin", "main")

            (repo / "feature.txt").write_text("hello gitflow\n", encoding="utf-8")

            agent = GitFlowAgent(
                repo_path=repo,
                main_branch="main",
                pr_backend=DryRunPullRequestBackend(),
            )

            plan = agent.process_change(
                feature_name="Integration Feature",
                commit_message="feat: integration feature",
                change_summary="End-to-end gitflow integration test",
                execute=True,
            )

            self.assertEqual(plan.feature_branch, "feature/integration-feature")
            self.assertTrue(plan.feature_pull_request.request.head.endswith("integration-feature"))

            with patch.object(
                GitFlowAgent,
                "run_code_review_ci",
                return_value=CIResult(
                    passed=True,
                    score=9.0,
                    models_used=["test"],
                    critical=0,
                    high=0,
                    medium=0,
                    low=0,
                    fix_instructions_path=None,
                ),
            ):
                merge_plan = agent.merge_feature_into_main(
                    feature_name="Integration Feature",
                    execute=True,
                    delete_feature_branch=True,
                    delete_local=True,
                    delete_remote=True,
                    skip_ci=False,
                )

            self.assertEqual(merge_plan.feature_branch, "feature/integration-feature")

            current_branch = self._git(repo, "branch", "--show-current").stdout.strip()
            self.assertEqual(current_branch, "main")

            feature_local_exists = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "--verify", "feature/integration-feature"],
                check=False,
                capture_output=True,
                text=True,
            ).returncode == 0
            self.assertFalse(feature_local_exists)

            self._git(repo, "fetch", "origin", "--prune")
            feature_remote_exists = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "--verify", "origin/feature/integration-feature"],
                check=False,
                capture_output=True,
                text=True,
            ).returncode == 0
            self.assertFalse(feature_remote_exists)

    def test_end_to_end_merge_cleanup_rerun_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            remote = tmp_path / "remote.git"
            repo = tmp_path / "repo"

            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True, text=True)

            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            self._git(repo, "config", "user.name", "GitFlow Test")
            self._git(repo, "config", "user.email", "gitflow-test@example.com")
            self._git(repo, "branch", "-M", "main")
            self._git(repo, "remote", "add", "origin", str(remote))

            (repo / "README.md").write_text("# rerun integration test\n", encoding="utf-8")
            self._git(repo, "add", "README.md")
            self._git(repo, "commit", "-m", "chore: initial commit")
            self._git(repo, "push", "-u", "origin", "main")

            (repo / "feature-rerun.txt").write_text("first pass\n", encoding="utf-8")

            agent = GitFlowAgent(
                repo_path=repo,
                main_branch="main",
                pr_backend=DryRunPullRequestBackend(),
            )

            agent.process_change(
                feature_name="Rerun Feature",
                commit_message="feat: rerun feature",
                change_summary="Integration rerun idempotency test",
                execute=True,
            )

            ci_ok = CIResult(
                passed=True,
                score=9.0,
                models_used=["test"],
                critical=0,
                high=0,
                medium=0,
                low=0,
                fix_instructions_path=None,
            )

            with patch.object(GitFlowAgent, "run_code_review_ci", return_value=ci_ok):
                first_merge = agent.merge_feature_into_main(
                    feature_name="Rerun Feature",
                    execute=True,
                    delete_feature_branch=True,
                    delete_local=True,
                    delete_remote=True,
                    skip_ci=False,
                )

            self.assertEqual(first_merge.feature_branch, "feature/rerun-feature")

            # Re-run merge+cleanup after branch has already been merged/deleted.
            with patch.object(GitFlowAgent, "run_code_review_ci", return_value=ci_ok):
                second_merge = agent.merge_feature_into_main(
                    feature_name="Rerun Feature",
                    execute=True,
                    delete_feature_branch=True,
                    delete_local=True,
                    delete_remote=True,
                    skip_ci=False,
                )

            self.assertEqual(second_merge.feature_branch, "feature/rerun-feature")

            current_branch = self._git(repo, "branch", "--show-current").stdout.strip()
            self.assertEqual(current_branch, "main")

            self._git(repo, "fetch", "origin", "--prune")
            feature_local_exists = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "--verify", "feature/rerun-feature"],
                check=False,
                capture_output=True,
                text=True,
            ).returncode == 0
            feature_remote_exists = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "--verify", "origin/feature/rerun-feature"],
                check=False,
                capture_output=True,
                text=True,
            ).returncode == 0
            self.assertFalse(feature_local_exists)
            self.assertFalse(feature_remote_exists)


if __name__ == "__main__":
    unittest.main()
