from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# Allow importing sibling agents regardless of how this script is invoked
_repo_root = Path(__file__).parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from agents.code_review_agent import (  # noqa: E402
    CodeReviewAgent as _CodeReviewAgent,
    Finding as _Finding,
    ReviewResult as _ReviewResult,
    Severity as _Severity,
    _available_models as _available_review_models,
    _load_dotenv as _load_review_dotenv,
)

_logger = logging.getLogger(__name__)
logging.basicConfig(format="[%(levelname)s] %(message)s", level=logging.INFO)

# ---------------------------------------------------------------------------
# CI gate types
# ---------------------------------------------------------------------------

# File-path prefixes used to assign findings to developer agents
_FRONTEND_PREFIXES = ("generated/frontend-app/", "frontend/", "src/components/", "src/pages/", "app/")
_BACKEND_PREFIXES  = ("generated/backend-app/", "backend/", "api/", "models/", "views/", "migrations/")


@dataclass(frozen=True)
class CIResult:
    passed: bool
    score: float
    models_used: list[str]
    critical: int
    high: int
    medium: int
    low: int
    fix_instructions_path: Path | None

    def summary(self) -> str:
        if self.passed:
            return (
                f"CI PASSED  score={self.score:.1f}/10  low={self.low}"
            )
        return (
            f"CI FAILED  score={self.score:.1f}/10  "
            f"critical={self.critical}  high={self.high}  medium={self.medium}  low={self.low}"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "score": self.score,
            "models_used": self.models_used,
            "critical": self.critical,
            "high": self.high,
            "medium": self.medium,
            "low": self.low,
            "fix_instructions_path": str(self.fix_instructions_path) if self.fix_instructions_path else None,
        }


class CIBlockedError(RuntimeError):
    """Raised when the code review CI gate blocks a merge."""

    def __init__(self, message: str, ci_result: CIResult) -> None:
        super().__init__(message)
        self.ci_result = ci_result


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


@dataclass(frozen=True)
class MergeToMainPlan:
    feature_branch: str
    merge_commands: list[list[str]]
    cleanup: BranchCleanupPlan | None

    def to_dict(self) -> dict[str, object]:
        return {
            "feature_branch": self.feature_branch,
            "merge_commands": self.merge_commands,
            "cleanup": self.cleanup.to_dict() if self.cleanup else None,
        }


# Backward-compatible type alias for older integrations.
MergeToMasterPlan = MergeToMainPlan


def _local_branch_exists(repo_path: "Path", branch: str) -> bool:
    """Return True if *branch* exists as a local branch in the given repo."""
    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "--verify", branch],
        capture_output=True,
    )
    return result.returncode == 0


def _remote_branch_exists(repo_path: "Path", branch: str) -> bool:
    """Return True if *branch* exists as a remote-tracking branch."""
    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "--verify", f"origin/{branch}"],
        capture_output=True,
    )
    return result.returncode == 0


class GitFlowAgent:
    def __init__(
        self,
        repo_path: str | Path,
        main_branch: str = "main",
        pr_backend: PullRequestBackend | None = None,
    ) -> None:
        self.repo_path = Path(repo_path)
        self.main_branch = main_branch
        self.pr_backend = pr_backend or GitHubPullRequestBackend.from_environment() or DryRunPullRequestBackend()

    def _run_git(
        self,
        args: list[str],
        *,
        check: bool = True,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        # Pre-seed answers to avoid blocking prompts on Windows branch-ref cleanup.
        return subprocess.run(
            ["git", "-C", str(self.repo_path), *args],
            check=check,
            capture_output=capture_output,
            text=True,
            input="n\n",
        )

    def _has_staged_changes(self) -> bool:
        result = self._run_git(["diff", "--cached", "--quiet"], check=False)
        return result.returncode != 0

    def _is_ancestor(self, older_ref: str, newer_ref: str) -> bool:
        result = self._run_git(["merge-base", "--is-ancestor", older_ref, newer_ref], check=False)
        return result.returncode == 0

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
            ["git", "-C", str(self.repo_path), "checkout", self.main_branch],
            ["git", "-C", str(self.repo_path), "pull", "--ff-only", "origin", self.main_branch],
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
            self._run_git(["fetch", "origin"])
            self._run_git(["checkout", self.main_branch])
            self._run_git(["pull", "--ff-only", "origin", self.main_branch])

            if _local_branch_exists(self.repo_path, feature_branch):
                self._run_git(["checkout", feature_branch])
            else:
                self._run_git(["checkout", "-b", feature_branch])

            if stage_all:
                self._run_git(["add", "-A"])

            if self._has_staged_changes():
                self._run_git(["commit", "-m", commit_message])
            else:
                _logger.info("No staged changes detected; skipping commit.")

            # Always push so reruns update upstream tracking and remote branch state.
            self._run_git(["push", "-u", "origin", feature_branch])

        feature_pr = self._create_pull_request(
            PullRequestRequest(
                title=f"Merge {feature_branch} into {self.main_branch}",
                body=change_summary,
                head=feature_branch,
                base=self.main_branch,
            )
        )
        return GitFlowPlan(
            feature_branch=feature_branch,
            commands=commands,
            feature_pull_request=feature_pr,
        )

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
            self._run_git(["fetch", "origin"])
            # Use origin/branch for ancestor check so it works in fresh clones without local tracking branches
            if _local_branch_exists(self.repo_path, feature_branch):
                ancestor_ref = feature_branch
            elif _remote_branch_exists(self.repo_path, feature_branch):
                ancestor_ref = f"origin/{feature_branch}"
            else:
                _logger.info("Feature branch %s does not exist locally or remotely; cleanup is idempotent no-op.", feature_branch)
                return BranchCleanupPlan(
                    feature_branch=feature_branch,
                    local_commands=local_commands,
                    remote_commands=remote_commands,
                )

            if not self._is_ancestor(ancestor_ref, self.main_branch):
                raise RuntimeError(
                    f"Cannot clean branch {feature_branch}: it is not merged into {self.main_branch}."
                )

            for command in local_commands:
                result = self._run_git(command[3:], check=False, capture_output=True)
                if result.returncode != 0:
                    _logger.warning("Local branch cleanup skipped for %s: %s", feature_branch, (result.stderr or "").strip())

            for command in remote_commands:
                result = self._run_git(command[3:], check=False, capture_output=True)
                if result.returncode != 0:
                    stderr = (result.stderr or "").lower()
                    if "remote ref does not exist" in stderr:
                        _logger.info("Remote branch %s already deleted.", feature_branch)
                    else:
                        _logger.warning("Remote branch cleanup skipped for %s: %s", feature_branch, (result.stderr or "").strip())

        return BranchCleanupPlan(
            feature_branch=feature_branch,
            local_commands=local_commands,
            remote_commands=remote_commands,
        )

    # ------------------------------------------------------------------
    # Code review CI gate
    # ------------------------------------------------------------------

    def run_code_review_ci(
        self,
        feature_branch: str,
        base_branch: str,
    ) -> CIResult:
        """Run the code review agent as a CI gate before merging.

        Loads credentials from ``.env``, runs all available AI models, and
        returns a :class:`CIResult`.  The merge is considered blocked if any
        Critical, High or Medium findings are present.  When blocked, a
        ``review-fix-instructions.md`` file is written to the repo root with
        findings partitioned by developer agent responsibility (frontend /
        backend / general).
        """
        _load_review_dotenv(self.repo_path)
        models = _available_review_models()

        if not models:
            _logger.warning(
                "No AI credentials found — skipping code review gate. "
                "Set GITHUB_TOKEN in .env to enable CI gating."
            )
            return CIResult(
                passed=True, score=0.0, models_used=[],
                critical=0, high=0, medium=0, low=0,
                fix_instructions_path=None,
            )

        _logger.info("Running code review: %s → %s", feature_branch, base_branch)
        agent = _CodeReviewAgent()
        result: _ReviewResult = agent.review(
            repo_path=self.repo_path,
            commit=feature_branch,
            base=base_branch,
            models=models,
            write_report=True,
            patch_agents=True,
        )

        by_sev = result.findings_by_severity()
        critical = len(by_sev[_Severity.CRITICAL])
        high     = len(by_sev[_Severity.HIGH])
        medium   = len(by_sev[_Severity.MEDIUM])
        low      = len(by_sev[_Severity.LOW])

        # Require at least one model to have succeeded; if every model failed
        # we cannot vouch for code quality and must block the merge.
        if not result.model_reviews:
            _logger.error(
                "All AI models failed — cannot assess code quality. "
                "Merge blocked until at least one model completes a review. "
                "Check GITHUB_TOKEN validity and network connectivity."
            )
            return CIResult(
                passed=False, score=0.0, models_used=[],
                critical=0, high=0, medium=0, low=0,
                fix_instructions_path=None,
            )

        passed   = (critical + high + medium) == 0

        fix_path: Path | None = None
        if not passed:
            fix_path = self._write_fix_instructions(result, feature_branch)

        return CIResult(
            passed=passed,
            score=result.overall_score(),
            models_used=[r.model for r in result.model_reviews],
            critical=critical,
            high=high,
            medium=medium,
            low=low,
            fix_instructions_path=fix_path,
        )

    def _write_fix_instructions(
        self,
        result: "_ReviewResult",
        feature_branch: str,
    ) -> Path:
        """Write ``review-fix-instructions.md`` partitioned by developer agent.

        Findings are routed to the Frontend Developer Agent, Backend Developer
        Agent, or a general Fullstack bucket based on the changed file path.
        Consensus findings (agreed by ≥ 2 models) are highlighted at the top
        so they are fixed first.
        """
        actionable = {_Severity.CRITICAL, _Severity.HIGH, _Severity.MEDIUM}

        # Deduplicate and collect actionable findings across all models
        seen: set[str] = set()
        unique: list[_Finding] = []
        for finding in sorted(
            (f for r in result.model_reviews for f in r.findings if f.severity in actionable),
            key=lambda f: f.severity.priority(),
            reverse=True,
        ):
            if finding.key() not in seen:
                seen.add(finding.key())
                unique.append(finding)

        # Partition by developer agent responsibility
        frontend: list[_Finding] = []
        backend:  list[_Finding] = []
        general:  list[_Finding] = []
        for f in unique:
            fp = f.file.lower().replace("\\", "/")
            if any(fp.startswith(p) for p in _FRONTEND_PREFIXES):
                frontend.append(f)
            elif any(fp.startswith(p) for p in _BACKEND_PREFIXES):
                backend.append(f)
            else:
                general.append(f)

        lines: list[str] = [
            "# Code Review Fix Instructions",
            "",
            f"> Generated by GitFlow CI gate for branch `{feature_branch}`  ",
            f"> Overall quality score: **{result.overall_score():.1f}/10**  ",
            "> **Merge is BLOCKED** until all Critical, High and Medium findings are resolved.",
            "",
            "## Instructions for developer agents",
            "",
            "1. Fix every finding listed below (Critical → High → Medium order).",
            "2. Commit with message: `fix: address code review findings from CI gate`",
            "3. Push to the feature branch.",
            "4. Re-run the GitFlow merge — CI will re-run automatically.",
            "",
        ]

        # Consensus callout (highest urgency)
        actionable_consensus = [
            ci for ci in result.consensus
            if ci.canonical.severity in actionable
        ]
        if actionable_consensus:
            lines += [
                "---",
                "",
                "## Priority: Consensus issues (agreed by ≥ 2 models)",
                "",
                "> Fix these first — independently flagged by multiple AI models.",
                "",
            ]
            for ci in actionable_consensus:
                f = ci.canonical
                lines += [
                    f"- {f.severity.emoji()} **[{f.severity.value.upper()}] {f.title}**",
                    f"  - File: `{f.file}`{(' line ' + str(f.line)) if f.line else ''}",
                    f"  - Agreed by: {', '.join(ci.agreed_by)}",
                    f"  - Fix: {f.suggestion}",
                    "",
                ]

        def _render_section(title: str, agent_label: str, findings: list[_Finding]) -> list[str]:
            if not findings:
                return []
            out: list[str] = [
                "---",
                "",
                f"## {title}",
                f"**Assigned to: {agent_label}**",
                "",
            ]
            for f in findings:
                out += [
                    f"### {f.severity.emoji()} `{f.severity.value.upper()}` — {f.title}",
                    "",
                    f"- **File**: `{f.file}`{(' line ' + str(f.line)) if f.line else ''}",
                    f"- **Dimension**: {f.dimension.value}",
                    f"- **Detected by**: {f.model}",
                    "",
                    f"**Issue**: {f.detail}",
                    "",
                    f"**Suggested fix**: {f.suggestion}",
                    "",
                ]
            return out

        lines += _render_section("Frontend findings", "Frontend Developer Agent", frontend)
        lines += _render_section("Backend findings",  "Backend Developer Agent",  backend)
        lines += _render_section("General / Agent findings", "Fullstack Developer Agent", general)

        out_path = self.repo_path / "review-fix-instructions.md"
        out_path.write_text("\n".join(lines), encoding="utf-8")
        _logger.info("Fix instructions → %s", out_path)
        return out_path

    def merge_feature_into_main(
        self,
        feature_name: str,
        execute: bool = False,
        delete_feature_branch: bool = True,
        delete_local: bool = True,
        delete_remote: bool = True,
        skip_ci: bool = False,
    ) -> MergeToMainPlan:
        feature_branch = f"feature/{self._slugify(feature_name)}"

        # --- CI gate ---------------------------------------------------
        # When actually executing, run the code review before touching main.
        # Pass skip_ci=True (or --skip-ci on CLI) only in emergencies.
        if execute and not skip_ci:
            ci_result = self.run_code_review_ci(feature_branch, self.main_branch)
            if ci_result.passed:
                _logger.info(ci_result.summary())
            else:
                _logger.error(ci_result.summary())
                _logger.error(
                    "MERGE BLOCKED — resolve all Critical/High/Medium findings. "
                    "Fix instructions: %s. "
                    "Developer agents: fix findings → commit → push → re-run merge.",
                    ci_result.fix_instructions_path,
                )
                raise CIBlockedError(
                    f"Code review gate failed: "
                    f"{ci_result.critical} critical, {ci_result.high} high, "
                    f"{ci_result.medium} medium findings remain unresolved.",
                    ci_result=ci_result,
                )

        merge_commands = [
            ["git", "-C", str(self.repo_path), "fetch", "origin"],
            ["git", "-C", str(self.repo_path), "checkout", self.main_branch],
            ["git", "-C", str(self.repo_path), "pull", "--ff-only", "origin", self.main_branch],
            ["git", "-C", str(self.repo_path), "merge", "--no-ff", f"origin/{feature_branch}"],
            ["git", "-C", str(self.repo_path), "push", "origin", self.main_branch],
        ]

        if execute:
            self._run_git(["fetch", "origin"])
            self._run_git(["checkout", self.main_branch])
            self._run_git(["pull", "--ff-only", "origin", self.main_branch])

            upstream_feature = f"origin/{feature_branch}"
            local_exists = _local_branch_exists(self.repo_path, feature_branch)
            remote_exists = _remote_branch_exists(self.repo_path, feature_branch)

            if remote_exists and not self._is_ancestor(upstream_feature, self.main_branch):
                self._run_git(["merge", "--no-ff", upstream_feature])
                self._run_git(["push", "origin", self.main_branch])
            elif local_exists and not self._is_ancestor(feature_branch, self.main_branch):
                self._run_git(["merge", "--no-ff", feature_branch])
                self._run_git(["push", "origin", self.main_branch])
            else:
                _logger.info("Feature branch %s is already merged into %s; skipping merge/push.", feature_branch, self.main_branch)

        cleanup_plan: BranchCleanupPlan | None = None
        if delete_feature_branch:
            cleanup_plan = self.cleanup_merged_feature_branch(
                feature_name=feature_name,
                execute=execute,
                delete_local=delete_local,
                delete_remote=delete_remote,
            )

        return MergeToMainPlan(
            feature_branch=feature_branch,
            merge_commands=merge_commands,
            cleanup=cleanup_plan,
        )

    # Backward-compatibility shim for earlier API name.
    def merge_feature_into_master(
        self,
        feature_name: str,
        execute: bool = False,
        delete_feature_branch: bool = True,
        delete_local: bool = True,
        delete_remote: bool = True,
        skip_ci: bool = False,
    ) -> MergeToMainPlan:
        return self.merge_feature_into_main(
            feature_name=feature_name,
            execute=execute,
            delete_feature_branch=delete_feature_branch,
            delete_local=delete_local,
            delete_remote=delete_remote,
            skip_ci=skip_ci,
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
    parser = argparse.ArgumentParser(description="Run a GitFlow-style change plan using a main-based workflow.")
    parser.add_argument("--repo", default=".", help="Repository path.")
    parser.add_argument("--feature", required=True, help="Feature or change name.")
    parser.add_argument("--commit-message", default="", help="Commit message for the feature branch.")
    parser.add_argument("--summary", default="", help="Summary for the generated pull requests.")
    parser.add_argument("--main-branch", default="main", help="Main branch name.")
    parser.add_argument("--execute", action="store_true", help="Run git commands instead of producing a dry-run plan.")
    parser.add_argument(
        "--cleanup-feature-branch",
        action="store_true",
        help="Clean up a merged feature branch (local and/or remote).",
    )
    parser.add_argument(
        "--merge-feature-into-main",
        action="store_true",
        help="Merge a feature branch into main and optionally delete that feature branch.",
    )
    parser.add_argument(
        "--no-delete-feature-branch",
        action="store_true",
        help="When merging into main, keep the feature branch after merge.",
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
    parser.add_argument(
        "--skip-ci",
        action="store_true",
        help="Bypass the code review CI gate when merging (emergency use only).",
    )
    parser.add_argument(
        "--run-ci",
        action="store_true",
        help="Run the code review CI gate standalone and report results without merging.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    agent = GitFlowAgent(
        repo_path=args.repo,
        main_branch=args.main_branch,
    )
    if args.run_ci:
        feature_branch = f"feature/{GitFlowAgent._slugify(args.feature)}"
        ci_result = agent.run_code_review_ci(feature_branch, args.main_branch)
        _logger.info(ci_result.summary())
        print(json.dumps(ci_result.to_dict(), indent=2))
        return 0 if ci_result.passed else 2

    if args.cleanup_feature_branch:
        cleanup_plan = agent.cleanup_merged_feature_branch(
            feature_name=args.feature,
            execute=args.execute,
            delete_local=not args.no_delete_local,
            delete_remote=not args.no_delete_remote,
        )
        print(json.dumps(cleanup_plan.to_dict(), indent=2))
        return 0

    if args.merge_feature_into_main:
        try:
            merge_plan = agent.merge_feature_into_main(
                feature_name=args.feature,
                execute=args.execute,
                delete_feature_branch=not args.no_delete_feature_branch,
                delete_local=not args.no_delete_local,
                delete_remote=not args.no_delete_remote,
                skip_ci=args.skip_ci,
            )
        except CIBlockedError as exc:
            print(
                json.dumps({
                    "error": "ci_blocked",
                    "message": str(exc),
                    "ci": exc.ci_result.to_dict(),
                }, indent=2)
            )
            return 2
        print(json.dumps(merge_plan.to_dict(), indent=2))
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
