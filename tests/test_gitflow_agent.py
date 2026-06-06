from __future__ import annotations

import unittest
from unittest.mock import Mock

from agents.gitflow_agent import DryRunPullRequestBackend, GitFlowAgent, PullRequestResult


class GitFlowAgentTests(unittest.TestCase):
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
        self.assertEqual(plan.feature_pull_request.request.base, "dev")
        self.assertEqual(plan.release_pull_request.request.base, "master")
        self.assertEqual(plan.feature_pull_request.mode, "dry-run")
        self.assertIn("feature/requirements-agent", plan.feature_pull_request.request.title.lower())

    def test_sync_master_back_to_dev_uses_default_branches(self) -> None:
        agent = GitFlowAgent(
            repo_path="/tmp/workspace/DJHamSambo/Coaching-Platform",
            pr_backend=DryRunPullRequestBackend(),
        )

        commands = agent.sync_master_back_to_dev(execute=False)

        self.assertEqual(commands[0][-1], "dev")
        self.assertEqual(commands[2][-1], "master")

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
        self.assertEqual(plan.release_pull_request.mode, "dry-run")

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

    def test_merge_feature_into_master_cleans_up_feature_branch_by_default(self) -> None:
        agent = GitFlowAgent(
            repo_path="/tmp/workspace/DJHamSambo/Coaching-Platform",
            pr_backend=DryRunPullRequestBackend(),
        )

        merge_plan = agent.merge_feature_into_master(feature_name="Requirements Agent")

        self.assertEqual(merge_plan.feature_branch, "feature/requirements-agent")
        self.assertEqual(merge_plan.merge_commands[1][-1], "master")
        self.assertEqual(merge_plan.merge_commands[3][-2:], ["--no-ff", "feature/requirements-agent"])
        self.assertIsNotNone(merge_plan.cleanup)
        assert merge_plan.cleanup is not None
        self.assertEqual(merge_plan.cleanup.local_commands[0][-2:], ["-d", "feature/requirements-agent"])
        self.assertEqual(merge_plan.cleanup.remote_commands[0][-3:], ["origin", "--delete", "feature/requirements-agent"])

    def test_merge_feature_into_master_can_keep_feature_branch(self) -> None:
        agent = GitFlowAgent(
            repo_path="/tmp/workspace/DJHamSambo/Coaching-Platform",
            pr_backend=DryRunPullRequestBackend(),
        )

        merge_plan = agent.merge_feature_into_master(
            feature_name="Requirements Agent",
            delete_feature_branch=False,
        )

        self.assertIsNone(merge_plan.cleanup)


if __name__ == "__main__":
    unittest.main()
