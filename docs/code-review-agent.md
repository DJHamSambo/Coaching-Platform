# Code Review Agent

## Purpose

`agents/code_review_agent.py` performs expert, multi-model AI code review on every
git check-in.  It analyses changed files across five dimensions and aggregates findings
from multiple AI models to produce objective, consensus-driven feedback.

## Recommended setup — GitHub Copilot Models

A single `GITHUB_TOKEN` (available to all GitHub Copilot subscribers) unlocks three
distinct model architectures through the GitHub Models inference endpoint — ideal for
multi-model consensus without needing separate provider API keys.

Add to `.env` in the repo root:

```
GITHUB_TOKEN=ghp_...
```

| Model key | Model | Architecture |
|---|---|---|
| `github/gpt-4o` | GPT-4o | OpenAI transformer |
| `github/claude` | Claude Sonnet | Anthropic constitutional AI |
| `github/llama` | Meta Llama 4 Scout | Open-weight transformer |

## Review dimensions

| Dimension | What is checked |
|---|---|
| `coding_standards` | Style, naming, idioms, structure for the language |
| `security` | OWASP Top 10, secret leakage, injection, auth/authz flaws |
| `maintainability` | Complexity, coupling, readability, test coverage |
| `technical_debt` | Shortcuts, TODOs, dead code, duplication |
| `codebase_impact` | API surface changes, breaking contracts, dep graph effects |

## Multi-model objectivity

Findings flagged by **≥ 2 models** are promoted to *consensus* status and receive
the highest remediation priority in the report.

## Alternative backends (optional)

Direct provider API keys are also supported:

| Key | Model | Env var |
|---|---|---|
| `openai` | GPT-4o | `OPENAI_API_KEY` |
| `anthropic` | Claude Opus | `ANTHROPIC_API_KEY` |
| `gemini` | Gemini 2.5 Flash | `GEMINI_API_KEY` |

## Agent self-improvement

When a consensus issue originates from a file inside `agents/`, the agent appends
a structured patch note directly to the offending agent file so future iterations
of that agent are aware of the recurring defect category.

## Usage

```bash
# Review HEAD against its parent (uses all available models automatically)
python agents/code_review_agent.py --commit HEAD

# Review a specific commit against a branch
python agents/code_review_agent.py --commit abc123 --base main

# Review from a patch file
python agents/code_review_agent.py --diff-file /tmp/my.patch

# Use only specific models
python agents/code_review_agent.py --commit HEAD --models github/gpt-4o github/claude

# Regenerate this documentation
python agents/code_review_agent.py --commit HEAD --update-docs
```

## Options

| Flag | Default | Description |
|---|---|---|
| `--commit` | `HEAD` | Commit SHA or ref to review |
| `--base` | `HEAD~1` | Base ref for the diff |
| `--diff-file` | — | Read diff from a file instead of git |
| `--repo` | `.` | Path to the git repository |
| `--models` | all available | Space-separated model keys to use |
| `--no-patch-agents` | flag | Disable automatic agent patching |
| `--no-report` | flag | Skip writing the report file |
| `--update-docs` | flag | Regenerate docs/code-review-agent.md |

## Output

- `code-review-report.md` — full report written to repo root
- Inline patch notes appended to agent source files when consensus issues are found

## Environment variables

```
GITHUB_TOKEN        — recommended: unlocks github/gpt-4o, github/claude, github/llama
OPENAI_API_KEY      — optional: direct OpenAI access
ANTHROPIC_API_KEY   — optional: direct Anthropic access
GEMINI_API_KEY      — optional: direct Google Gemini access
```

## Notes

- Uses Python standard library only (no third-party dependencies).
- All AI calls use urllib with a 120-second timeout.
- Partial results are returned if a model fails.
- Diff content per file is capped at 8 000 characters to stay within model context limits.
- Agent version: 1.1.0
