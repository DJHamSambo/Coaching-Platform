from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class PullRequestRequest:
    title: str
    body: str
    head: str
    base: str


@dataclass(frozen=True)
class PullRequestResult:
    mode: str
    request: PullRequestRequest
    url: str | None = None
    number: int | None = None


class PullRequestBackend(Protocol):
    def create_pull_request(self, request: PullRequestRequest) -> PullRequestResult:
        ...


class DryRunPullRequestBackend:
    def create_pull_request(self, request: PullRequestRequest) -> PullRequestResult:
        return PullRequestResult(mode="dry-run", request=request)


class GitHubPullRequestBackend:
    def __init__(self, repository: str, token: str) -> None:
        self.repository = repository
        self.token = token

    @classmethod
    def from_environment(cls) -> GitHubPullRequestBackend | None:
        repository = os.getenv("GITHUB_REPOSITORY")
        token = os.getenv("GITHUB_TOKEN")
        if repository and token:
            return cls(repository=repository, token=token)
        return None

    def create_pull_request(self, request: PullRequestRequest) -> PullRequestResult:
        payload = json.dumps(asdict(request)).encode("utf-8")
        api_url = f"https://api.github.com/repos/{self.repository}/pulls"
        http_request = Request(
            api_url,
            data=payload,
            headers={
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "GitFlowAgent/1.0",
            },
            method="POST",
        )
        http_request.add_unredirected_header("Authorization", "Bearer " + self.token)
        try:
            with urlopen(http_request, timeout=15) as response:  # nosec B310
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Failed to create pull request: {detail or error.reason}") from error
        return PullRequestResult(
            mode="github",
            request=request,
            url=data.get("html_url"),
            number=data.get("number"),
        )


@dataclass(frozen=True)
class GitFlowPlan:
    feature_branch: str
    commands: list[list[str]]
    feature_pull_request: PullRequestResult
    release_pull_request: PullRequestResult

    def to_dict(self) -> dict[str, object]:
        return {
            "feature_branch": self.feature_branch,
            "commands": self.commands,
            "feature_pull_request": {
                "mode": self.feature_pull_request.mode,
                "title": self.feature_pull_request.request.title,
                "head": self.feature_pull_request.request.head,
                "base": self.feature_pull_request.request.base,
                "url": self.feature_pull_request.url,
                "number": self.feature_pull_request.number,
            },
            "release_pull_request": {
                "mode": self.release_pull_request.mode,
                "title": self.release_pull_request.request.title,
                "head": self.release_pull_request.request.head,
                "base": self.release_pull_request.request.base,
                "url": self.release_pull_request.url,
                "number": self.release_pull_request.number,
            },
        }


@dataclass(frozen=True)
class BranchCleanupPlan:
    feature_branch: str
    local_commands: list[list[str]]
    remote_commands: list[list[str]]

    def to_dict(self) -> dict[str, object]:
        return {
            "feature_branch": self.feature_branch,
            "local_commands": self.local_commands,
            "remote_commands": self.remote_commands,
        }


class GitFlowAgent:
    def __init__(
        self,
        repo_path: str | Path,
        dev_branch: str = "dev",
        master_branch: str = "master",
        pr_backend: PullRequestBackend | None = None,
    ) -> None:
        self.repo_path = Path(repo_path)
        self.dev_branch = dev_branch
        self.master_branch = master_branch
        self.pr_backend = pr_backend or GitHubPullRequestBackend.from_environment() or DryRunPullRequestBackend()

    def process_change(
        self,
        feature_name: str,
        commit_message: str,
        change_summary: str,
        execute: bool = False,
        stage_all: bool = True,
    ) -> GitFlowPlan:
        feature_branch = f"feature/{self._slugify(feature_name)}"
        commands = [
            ["git", "-C", str(self.repo_path), "fetch", "origin"],
            ["git", "-C", str(self.repo_path), "checkout", self.dev_branch],
            ["git", "-C", str(self.repo_path), "pull", "--ff-only", "origin", self.dev_branch],
            ["git", "-C", str(self.repo_path), "checkout", "-b", feature_branch],
        ]
        if stage_all:
            commands.append(["git", "-C", str(self.repo_path), "add", "-A"])
        commands.extend(
            [
                ["git", "-C", str(self.repo_path), "commit", "-m", commit_message],
                ["git", "-C", str(self.repo_path), "push", "-u", "origin", feature_branch],
            ]
        )

        if execute:
            for command in commands:
                subprocess.run(command, check=True)

        feature_pr = self._create_pull_request(
            PullRequestRequest(
                title=f"Merge {feature_branch} into {self.dev_branch}",
                body=change_summary,
                head=feature_branch,
                base=self.dev_branch,
            )
        )
        release_pr = self._create_pull_request(
            PullRequestRequest(
                title=f"Promote {self.dev_branch} into {self.master_branch}",
                body=f"Release changes for: {change_summary}",
                head=self.dev_branch,
                base=self.master_branch,
            )
        )
        return GitFlowPlan(
            feature_branch=feature_branch,
            commands=commands,
            feature_pull_request=feature_pr,
            release_pull_request=release_pr,
        )

    def sync_master_back_to_dev(self, execute: bool = False) -> list[list[str]]:
        commands = [
            ["git", "-C", str(self.repo_path), "checkout", self.dev_branch],
            ["git", "-C", str(self.repo_path), "pull", "--ff-only", "origin", self.dev_branch],
            ["git", "-C", str(self.repo_path), "merge", "--ff-only", self.master_branch],
            ["git", "-C", str(self.repo_path), "push", "origin", self.dev_branch],
        ]
        if execute:
            for command in commands:
                subprocess.run(command, check=True)
        return commands

    def cleanup_merged_feature_branch(
        self,
        feature_name: str,
        execute: bool = False,
        delete_local: bool = True,
        delete_remote: bool = True,
    ) -> BranchCleanupPlan:
        feature_branch = f"feature/{self._slugify(feature_name)}"
        local_commands: list[list[str]] = []
        remote_commands: list[list[str]] = []

        if delete_local:
            local_commands.append(["git", "-C", str(self.repo_path), "branch", "-d", feature_branch])
        if delete_remote:
            remote_commands.append(["git", "-C", str(self.repo_path), "push", "origin", "--delete", feature_branch])

        if execute:
            subprocess.run(["git", "-C", str(self.repo_path), "fetch", "origin"], check=True)
            subprocess.run(
                ["git", "-C", str(self.repo_path), "merge-base", "--is-ancestor", feature_branch, self.master_branch],
                check=True,
            )
            for command in local_commands + remote_commands:
                subprocess.run(command, check=True)

        return BranchCleanupPlan(
            feature_branch=feature_branch,
            local_commands=local_commands,
            remote_commands=remote_commands,
        )

    @staticmethod
    def _slugify(value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
        if not slug:
            raise ValueError("feature_name must contain at least one letter or number.")
        return slug

    def _create_pull_request(self, request: PullRequestRequest) -> PullRequestResult:
        try:
            return self.pr_backend.create_pull_request(request)
        except (OSError, RuntimeError):
            return DryRunPullRequestBackend().create_pull_request(request)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a GitFlow-style change plan using dev and master branches.")
    parser.add_argument("--repo", default=".", help="Repository path.")
    parser.add_argument("--feature", required=True, help="Feature or change name.")
    parser.add_argument("--commit-message", required=True, help="Commit message for the feature branch.")
    parser.add_argument("--summary", required=True, help="Summary for the generated pull requests.")
    parser.add_argument("--dev-branch", default="dev", help="Development branch name.")
    parser.add_argument("--master-branch", default="master", help="Production branch name.")
    parser.add_argument("--execute", action="store_true", help="Run git commands instead of producing a dry-run plan.")
    parser.add_argument(
        "--sync-master-back",
        action="store_true",
        help="Sync master back into the dev branch after release work is complete.",
    )
    parser.add_argument(
        "--cleanup-feature-branch",
        action="store_true",
        help="Clean up a merged feature branch (local and/or remote).",
    )
    parser.add_argument(
        "--no-delete-local",
        action="store_true",
        help="When cleaning up, do not delete the local feature branch.",
    )
    parser.add_argument(
        "--no-delete-remote",
        action="store_true",
        help="When cleaning up, do not delete the remote feature branch.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    agent = GitFlowAgent(
        repo_path=args.repo,
        dev_branch=args.dev_branch,
        master_branch=args.master_branch,
    )
    if args.sync_master_back:
        print(json.dumps({"commands": agent.sync_master_back_to_dev(execute=args.execute)}, indent=2))
        return 0

    if args.cleanup_feature_branch:
        cleanup_plan = agent.cleanup_merged_feature_branch(
            feature_name=args.feature,
            execute=args.execute,
            delete_local=not args.no_delete_local,
            delete_remote=not args.no_delete_remote,
        )
        print(json.dumps(cleanup_plan.to_dict(), indent=2))
        return 0

    plan = agent.process_change(
        feature_name=args.feature,
        commit_message=args.commit_message,
        change_summary=args.summary,
        execute=args.execute,
    )
    print(json.dumps(plan.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
