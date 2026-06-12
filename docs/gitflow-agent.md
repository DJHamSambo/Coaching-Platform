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

```bash
python agents/gitflow_agent.py \
  --repo . \
  --feature "requirements-agent" \
  --commit-message "feat: add requirements agent" \
  --summary "Add the requirements distillation agent and its documentation."
```

Merge a reviewed feature into `main` and clean up the feature branch:

```bash
python agents/gitflow_agent.py \
  --repo . \
  --feature "requirements-agent" \
  --merge-feature-into-main \
  --execute
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

## Notes

- The default mode is a safe dry run.
- Passing `--execute` runs the git commands directly.
- The mainline branch is configurable through `--main-branch` (default: `main`).
- In cleanup mode with `--execute`, the agent verifies the feature branch is merged into the configured `--main-branch` before deleting it.
- CI merge gating blocks merges when any Critical, High, or Medium code-review findings are present.
- Execution is idempotent for common reruns: existing feature branches are reused, empty commit attempts are skipped, already-merged branches skip merge/push, and missing branches during cleanup are treated as no-op.
