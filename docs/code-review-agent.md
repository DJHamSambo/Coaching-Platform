# Code Review Agent

## Purpose

`agents/code_review_agent.py` performs expert, multi-model AI code review on every
git check-in.  It analyses changed files across five dimensions and aggregates findings
from multiple AI models to produce objective, consensus-driven feedback.

## Review dimensions

| Dimension | What is checked |
|---|---|
| `coding_standards` | Style, naming, idioms, structure for the language |
| `security` | OWASP Top 10, secret leakage, injection, auth/authz flaws |
| `maintainability` | Complexity, coupling, readability, test coverage |
| `technical_debt` | Shortcuts, TODOs, dead code, duplication |
| `codebase_impact` | API surface changes, breaking contracts, dep graph effects |

## Multi-model objectivity

The agent calls up to three AI models and aggregates their findings:

| Key | Model | API key env var |
|---|---|---|
| `openai` | GPT-4o | `OPENAI_API_KEY` |
| `anthropic` | Claude Opus | `ANTHROPIC_API_KEY` |
| `gemini` | Gemini 2.5 Flash | `GEMINI_API_KEY` |

Findings flagged by **≥ 2 models** are promoted to *consensus* status and receive
the highest remediation priority in the report.

## Agent self-improvement

When a consensus issue originates from a file inside `agents/`, the agent appends
a structured patch note directly to the offending agent file so future iterations
of that agent are aware of the recurring defect category.

## Usage

```bash
# Review HEAD against its parent
python agents/code_review_agent.py --commit HEAD

# Review a specific commit against a branch
python agents/code_review_agent.py --commit abc123 --base main

# Review from a patch file
python agents/code_review_agent.py --diff-file /tmp/my.patch

# Use only specific models
python agents/code_review_agent.py --commit HEAD --models openai anthropic

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
OPENAI_API_KEY      — required for openai model
ANTHROPIC_API_KEY   — required for anthropic model
GEMINI_API_KEY      — required for gemini model
```

## Notes

- Uses Python standard library only (no third-party dependencies).
- All AI calls use urllib with a 120-second timeout.
- Partial results are returned if a model fails.
- Diff content per file is capped at 8 000 characters to stay within model context limits.
- Agent version: 1.0.0
