# Git Flow Agent

## Purpose

`agents/gitflow_agent.py` orchestrates a lightweight, main-based GitFlow process.

## What it does

- Creates a feature branch from `main`
- Stages and commits changes
- Pushes the feature branch
- Creates a pull request from the feature branch into `main`
- Runs the code review agent as a CI merge gate before merging
- Merges the feature branch into `main` when CI passes
- Deletes merged feature branches (local and remote)

## Pull request behaviour

- If `GITHUB_REPOSITORY` and `GITHUB_TOKEN` are present, the agent creates pull requests through the GitHub REST API.
- Otherwise it falls back to a dry-run mode and returns the PR payloads so another automation layer can submit them.
- If GitHub PR creation is configured but unavailable at runtime, the agent degrades to dry-run mode instead of failing the whole workflow.

## Usage

Create a feature branch with staged changes (default mode):

```bash
python agents/gitflow_agent.py \
  --repo . \
  --feature "requirements-agent" \
  --commit-message "feat: add requirements agent" \
  --summary "Add the requirements distillation agent and its documentation." \
  --execute
```

Or with the explicit (now deprecated) `--create-feature` flag:

```bash
python agents/gitflow_agent.py \
  --repo . \
  --feature "requirements-agent" \
  --commit-message "feat: add requirements agent" \
  --summary "Add the requirements distillation agent and its documentation." \
  --create-feature \
  --execute
```

Merge a reviewed feature into `main` and clean up the feature branch:

```bash
python agents/gitflow_agent.py \
  --repo . \
  --feature "requirements-agent" \
  --merge-feature-into-main \
  --execute
```

Merge with auto-remediation attempts when CI finds blocking issues:

```bash
python agents/gitflow_agent.py \
  --repo . \
  --feature "requirements-agent" \
  --merge-feature-into-main \
  --execute \
  --auto-implement \
  --max-auto-attempts 2
```

Run the code-review CI gate standalone:

```bash
python agents/gitflow_agent.py \
  --repo . \
  --feature "requirements-agent" \
  --run-ci
```

Cleanup options:

- `--cleanup-feature-branch` enables cleanup mode.
- `--no-delete-local` skips local branch deletion.
- `--no-delete-remote` skips remote branch deletion.

Auto-implement options:

- `--auto-implement` enables automatic remediation attempts when CI blocks merge.
- `--max-auto-attempts` controls retry count (default: `1`).
- `--auto-commit-message` sets commit message for auto-remediation commits.

## Notes

- **Feature branch creation is the default mode** when no action flag (`--merge-feature-into-main`, `--cleanup-feature-branch`, `--run-ci`) is specified.
- Passing `--create-feature` is deprecated but still accepted for backward compatibility; it does not change the default behavior.
- The default mode is a safe dry run.
- Passing `--execute` runs the git commands directly.
- The mainline branch is configurable through `--main-branch` (default: `main`).
- In cleanup mode with `--execute`, the agent verifies the feature branch is merged into the configured `--main-branch` before deleting it.
- CI merge gating blocks merges when any Critical, High, or Medium code-review findings are present.
- Execution is idempotent for common reruns: existing feature branches are reused, empty commit attempts are skipped, already-merged branches skip merge/push, and missing branches during cleanup are treated as no-op.
- With `--auto-implement`, the agent invokes the unified Developer Agent for end-to-end remediation, commits and pushes changes, then re-runs CI before deciding merge pass/fail.
