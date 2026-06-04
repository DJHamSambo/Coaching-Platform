# Git Flow Agent

## Purpose

`/tmp/workspace/DJHamSambo/Coaching-Platform/agents/gitflow_agent.py` orchestrates a lightweight GitFlow process using `dev` and `master` branches.

## What it does

- Creates a feature branch from `dev`
- Stages and commits changes
- Pushes the feature branch
- Creates a pull request from the feature branch into `dev`
- Creates a release pull request from `dev` into `master`
- Optionally syncs `master` back into `dev`
- Optionally cleans up merged feature branches (local and remote)

## Pull request behaviour

- If `GITHUB_REPOSITORY` and `GITHUB_TOKEN` are present, the agent creates pull requests through the GitHub REST API.
- Otherwise it falls back to a dry-run mode and returns the PR payloads so another automation layer can submit them.
- If GitHub PR creation is configured but unavailable at runtime, the agent degrades to dry-run mode instead of failing the whole workflow.

## Usage

```bash
python /tmp/workspace/DJHamSambo/Coaching-Platform/agents/gitflow_agent.py \
  --repo /tmp/workspace/DJHamSambo/Coaching-Platform \
  --feature "requirements-agent" \
  --commit-message "feat: add requirements agent" \
  --summary "Add the requirements distillation agent and its documentation."
```

Sync `master` back to `dev` after a release:

```bash
python /tmp/workspace/DJHamSambo/Coaching-Platform/agents/gitflow_agent.py \
  --repo /tmp/workspace/DJHamSambo/Coaching-Platform \
  --feature "unused" \
  --commit-message "unused" \
  --summary "unused" \
  --sync-master-back
```

Clean up a merged feature branch:

```bash
python /tmp/workspace/DJHamSambo/Coaching-Platform/agents/gitflow_agent.py \
  --repo /tmp/workspace/DJHamSambo/Coaching-Platform \
  --feature "requirements-agent" \
  --commit-message "unused" \
  --summary "unused" \
  --cleanup-feature-branch
```

Cleanup options:

- `--cleanup-feature-branch` enables cleanup mode.
- `--no-delete-local` skips local branch deletion.
- `--no-delete-remote` skips remote branch deletion.

## Notes

- The default mode is a safe dry run.
- Passing `--execute` runs the git commands directly.
- The agent keeps the branch names configurable through `--dev-branch` and `--master-branch`.
- In cleanup mode with `--execute`, the agent verifies the feature branch is merged into the configured `--master-branch` before deleting it.
