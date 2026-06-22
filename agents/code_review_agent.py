from __future__ import annotations

"""Code Review Agent
===================
Performs expert, multi-model AI code review on every check-in.

Review dimensions
-----------------
* **Coding standards** — style, idioms, naming, structure
* **Security** — OWASP Top 10, secret leakage, injection, auth flaws
* **Maintainability** — complexity, coupling, test coverage, readability
* **Technical debt** — shortcuts, TODOs, dead code, duplication
* **Codebase impact** — API surface changes, breaking contracts, dep graph effects

Multi-model objectivity
-----------------------
The agent calls multiple AI models and aggregates their findings.  Findings
flagged by 2 or more models are elevated to *consensus* status and receive
the highest remediation priority.

Preferred backend — GitHub Copilot Models
-----------------------------------------
A single ``GITHUB_TOKEN`` (available to all GitHub Copilot subscribers) unlocks
three distinct models through the GitHub Models inference endpoint:

* ``github/gpt-4o``    — OpenAI GPT-4o via GitHub
* ``github/claude``    — Anthropic Claude Sonnet via GitHub
* ``github/llama``     — Meta Llama 4 Scout via GitHub

Set ``GITHUB_TOKEN`` in ``.env`` and the agent auto-selects all three,
providing full consensus analysis without any separate paid API keys.

Alternative backends (optional)
--------------------------------
Direct API keys are also supported as fallback:
    OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY

Agent self-improvement
----------------------
When consensus issues originate from agent source files (``agents/``), the
agent writes targeted patch suggestions directly back to the offending agent
so the same category of defect will not recur.

Usage
-----
    python agents/code_review_agent.py --commit HEAD
    python agents/code_review_agent.py --commit abc123 --base main
    python agents/code_review_agent.py --diff-file /tmp/my.patch
    python agents/code_review_agent.py --commit HEAD --models github/gpt-4o github/claude
    python agents/code_review_agent.py --commit HEAD --update-docs

Chat handoff (no API key required)
----------------------------------
Run with ``--emit-prompt`` to capture the diff and review instructions into a
single request file (default ``generated/code-review-request.md``) instead of
calling any external model.  Open that file in an interactive chat agent and ask
for the review — the agent reviews the change with full repository context
(reading related files, running tests, tracing callers), the same way it would
if you asked directly in chat::

    python agents/code_review_agent.py --emit-prompt --commit HEAD --base main
    python agents/code_review_agent.py --emit-prompt --out my-review-request.md

Environment variables
---------------------
    GITHUB_TOKEN        — required for github/* models (recommended)
    OPENAI_API_KEY      — required for openai model
    ANTHROPIC_API_KEY   — required for anthropic model
    GEMINI_API_KEY      — required for gemini model
"""

import argparse
import datetime as dt
import fnmatch
import json
import os
import re
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


def _load_dotenv(repo_path: Path) -> None:
    """Load key=value pairs from .env in repo root into os.environ (no-op if absent)."""
    env_file = repo_path / ".env"
    if not env_file.exists():
        return
    # Read as bytes then decode, stripping UTF-8 BOM if PowerShell wrote one
    raw = env_file.read_bytes().decode("utf-8-sig")
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:   # env var takes precedence over .env
            os.environ[key] = value
from typing import Iterator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"
    INFO     = "info"

    def emoji(self) -> str:
        return {"critical": "🔴", "high": "🟠", "medium": "🟡",
                "low": "🔵", "info": "⚪"}[self.value]

    def priority(self) -> int:
        return {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}[self.value]


class Dimension(str, Enum):
    SECURITY        = "security"
    STANDARDS       = "coding_standards"
    MAINTAINABILITY = "maintainability"
    TECH_DEBT       = "technical_debt"
    IMPACT          = "codebase_impact"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DiffFile:
    path: str
    old_path: str | None
    is_new: bool
    is_deleted: bool
    hunks: list[str]

    @property
    def extension(self) -> str:
        return Path(self.path).suffix.lower()

    @property
    def is_agent(self) -> bool:
        return self.path.startswith("agents/") and self.path.endswith(".py")

    @property
    def content_snippet(self) -> str:
        """Return a compact representation safe to embed in a prompt."""
        lines: list[str] = []
        for hunk in self.hunks:
            lines.append(hunk)
            if sum(len(l) for l in lines) > 8_000:
                break
        return "\n".join(lines)[:8_000]


@dataclass(frozen=True)
class Finding:
    dimension:   Dimension
    severity:    Severity
    file:        str
    line:        int | None
    title:       str
    detail:      str
    suggestion:  str
    model:       str

    def key(self) -> str:
        """Deterministic key for deduplication / consensus detection."""
        return f"{self.dimension.value}::{self.severity.value}::{self.file}::{self.title[:60]}"


@dataclass
class ModelReview:
    model:     str
    findings:  list[Finding]
    summary:   str
    score:     int          # 0-10 quality score (10 = perfect)
    raw:       str          # raw model response for audit trail

    def finding_keys(self) -> set[str]:
        return {f.key() for f in self.findings}


@dataclass
class ConsensusIssue:
    """A finding agreed upon by ≥ 2 models — highest priority for remediation."""
    key:         str
    findings:    list[Finding]   # one per model
    agreed_by:   list[str]       # model names

    @property
    def canonical(self) -> Finding:
        """Return the highest-severity finding as the representative."""
        return max(self.findings, key=lambda f: f.severity.priority())

    @property
    def is_agent_issue(self) -> bool:
        return self.canonical.file.startswith("agents/")


@dataclass
class AgentPatch:
    """A targeted improvement suggestion written back to a source agent."""
    target_agent: str
    issue_title:  str
    dimension:    Dimension
    severity:     Severity
    suggestion:   str


@dataclass
class ReviewResult:
    commit:          str
    base:            str
    repo_path:       str
    timestamp:       str
    model_reviews:   list[ModelReview]
    consensus:       list[ConsensusIssue]
    agent_patches:   list[AgentPatch]
    files_reviewed:  list[str]

    def overall_score(self) -> float:
        if not self.model_reviews:
            return 0.0
        return round(sum(r.score for r in self.model_reviews) / len(self.model_reviews), 1)

    def all_findings(self) -> Iterator[Finding]:
        for review in self.model_reviews:
            yield from review.findings

    def findings_by_severity(self) -> dict[Severity, list[Finding]]:
        out: dict[Severity, list[Finding]] = {s: [] for s in Severity}
        for f in self.all_findings():
            out[f.severity].append(f)
        return out


# ---------------------------------------------------------------------------
# Diff extraction
# ---------------------------------------------------------------------------

class DiffParser:
    """Parse unified diff text into structured DiffFile objects."""

    _FILE_HEADER = re.compile(
        r"^diff --git a/(.+?) b/(.+?)$", re.MULTILINE
    )
    _NEW_FILE    = re.compile(r"^new file mode", re.MULTILINE)
    _DEL_FILE    = re.compile(r"^deleted file mode", re.MULTILINE)
    _RENAME_FROM = re.compile(r"^rename from (.+)$", re.MULTILINE)
    _HUNK        = re.compile(r"^@@[^@@]+@@.*$", re.MULTILINE)

    def parse(self, raw: str) -> list[DiffFile]:
        segments = self._FILE_HEADER.split(raw)
        # segments: [prefix, a_path, b_path, body, a_path, b_path, body, ...]
        files: list[DiffFile] = []
        i = 1
        while i < len(segments) - 2:
            a_path = segments[i].strip()
            b_path = segments[i + 1].strip()
            body   = segments[i + 2]
            is_new = bool(self._NEW_FILE.search(body))
            is_del = bool(self._DEL_FILE.search(body))
            rename = self._RENAME_FROM.search(body)
            old_path = rename.group(1).strip() if rename else None

            hunks = self._split_hunks(body)
            files.append(DiffFile(
                path=b_path,
                old_path=old_path,
                is_new=is_new,
                is_deleted=is_del,
                hunks=hunks,
            ))
            i += 3
        return files

    def _split_hunks(self, body: str) -> list[str]:
        positions = [m.start() for m in self._HUNK.finditer(body)]
        if not positions:
            return []
        hunks = []
        for idx, pos in enumerate(positions):
            end = positions[idx + 1] if idx + 1 < len(positions) else len(body)
            hunks.append(body[pos:end].strip())
        return hunks


def get_diff_from_git(repo_path: Path, commit: str, base: str) -> str:
    cmd = ["git", "-C", str(repo_path), "diff", f"{base}..{commit}"]
    # Decode explicitly as UTF-8 so Windows console code pages cannot break
    # subprocess text decoding for large/binary-adjacent diffs.
    result = subprocess.run(cmd, capture_output=True, text=False, check=True)
    return result.stdout.decode("utf-8", errors="replace")


def get_diff_from_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# AI model clients (stdlib urllib only)
# ---------------------------------------------------------------------------

def _http_post(url: str, headers: dict[str, str], payload: dict) -> str:
    """Send a JSON POST and return the response body as str."""
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(url, data=data, headers=headers, method="POST")
    timeout_seconds = _http_timeout_seconds()
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body[:500]}") from exc


def _build_review_prompt(diff_files: list[DiffFile], model_name: str) -> str:
    files_text = []
    for df in diff_files:
        if not df.content_snippet:
            continue
        files_text.append(f"### {df.path}\n```\n{df.content_snippet}\n```")

    joined = "\n\n".join(files_text) if files_text else "(no diff content)"

    return textwrap.dedent(f"""
        You are an expert senior software engineer conducting a rigorous code review.
        Your job is to critique the following git diff with unflinching honesty.

        Review across FIVE dimensions:
        1. coding_standards — style, naming, structure, idioms for the language
        2. security — OWASP Top 10, secret leakage, injection, auth/authz flaws
        3. maintainability — complexity, coupling, readability, test coverage
        4. technical_debt — shortcuts, TODOs, dead code, code duplication
        5. codebase_impact — API surface changes, breaking contracts, dependency effects

        For EACH finding, respond with EXACTLY this JSON object in a ```json block:
        {{
          "dimension": "<one of the five above>",
          "severity": "<critical|high|medium|low|info>",
          "file": "<file path>",
          "line": <integer or null>,
          "title": "<short title ≤ 60 chars>",
          "detail": "<full explanation>",
          "suggestion": "<concrete fix or improvement>"
        }}

        After all findings output a final ```json block with the review summary:
        {{
          "summary": "<2-4 sentence overall assessment>",
          "score": <integer 0-10 where 10 is production-perfect code>
        }}

        Be precise. Be critical. Do not praise mediocre code.
        Model: {model_name}

        --- DIFF ---
        {joined}
    """).strip()



def _build_chat_review_request(
    diff_files: list[DiffFile],
    commit: str,
    base: str,
    timestamp: str,
) -> str:
    """Build a self-contained review request for an interactive chat agent.

    Unlike ``_build_review_prompt`` (which asks an API model for strict JSON),
    this targets a chat agent that already has full repository access. It pairs
    the captured diff with instructions to read surrounding files, run checks,
    and reason across the codebase — i.e. review the change the way you would
    if asked directly in chat.
    """
    files_text: list[str] = []
    for df in diff_files:
        if not df.content_snippet:
            continue
        marker = "new file" if df.is_new else "modified"
        files_text.append(
            f"### `{df.path}` ({marker})\n\n```diff\n{df.content_snippet}\n```"
        )
    joined = "\n\n".join(files_text) if files_text else "_(no reviewable diff content)_"
    file_list = "\n".join(f"- `{df.path}`" for df in diff_files) or "- _(none)_"

    return "\n".join([
        "# Code Review Request (chat handoff)",
        "",
        "> Generated by code_review_agent.py for an interactive chat agent.",
        "> No external model was called — perform this review directly using full",
        "> repository context (read related files, run tests, trace callers).",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Commit | `{commit}` |",
        f"| Base | `{base}` |",
        f"| Timestamp | {timestamp} |",
        f"| Files in scope | {len(diff_files)} |",
        "",
        "## Files in scope",
        "",
        file_list,
        "",
        "## How to review",
        "",
        "Review this change as if the user asked you directly in chat. Do not limit",
        "yourself to the diff below — open the surrounding files, check callers and",
        "tests, and verify your findings against the actual codebase.",
        "",
        "Assess across five dimensions and call out the most important issues first:",
        "",
        "1. **coding_standards** — style, naming, structure, language idioms",
        "2. **security** — OWASP Top 10, secret leakage, injection, auth/authz flaws",
        "3. **maintainability** — complexity, coupling, readability, test coverage",
        "4. **technical_debt** — shortcuts, TODOs, dead code, duplication",
        "5. **codebase_impact** — API surface changes, breaking contracts, dep effects",
        "",
        "For each finding give: file/line, severity (critical/high/medium/low/info),",
        "the problem, and a concrete suggested fix. End with a short overall",
        "assessment and a 0–10 quality score.",
        "",
        "## Captured diff",
        "",
        joined,
        "",
    ])


def _parse_model_response(raw: str, model: str) -> ModelReview:
    """Extract structured findings and summary from a model's freeform response."""
    findings: list[Finding] = []
    summary = ""
    score   = 5

    for block in re.findall(r"```json\s*(.*?)\s*```", raw, flags=re.DOTALL):
        try:
            obj = json.loads(block)
        except json.JSONDecodeError:
            continue

        if "summary" in obj and "score" in obj:
            summary = str(obj.get("summary", ""))
            try:
                score = max(0, min(10, int(obj.get("score", 5))))
            except (TypeError, ValueError):
                score = 5
            continue

        try:
            dim = Dimension(obj.get("dimension", "maintainability"))
        except ValueError:
            dim = Dimension.MAINTAINABILITY
        try:
            sev = Severity(obj.get("severity", "medium"))
        except ValueError:
            sev = Severity.MEDIUM

        raw_line = obj.get("line")
        try:
            line = int(raw_line) if raw_line is not None else None
        except (TypeError, ValueError):
            line = None

        findings.append(Finding(
            dimension=dim,
            severity=sev,
            file=str(obj.get("file", "unknown")),
            line=line,
            title=str(obj.get("title", "Untitled"))[:120],
            detail=str(obj.get("detail", "")),
            suggestion=str(obj.get("suggestion", "")),
            model=model,
        ))

    if not summary:
        summary = "(model did not produce a structured summary)"

    return ModelReview(model=model, findings=findings, summary=summary, score=score, raw=raw)


def review_openai(diff_files: list[DiffFile], model_id: str = "gpt-4o") -> ModelReview:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    prompt = _build_review_prompt(diff_files, "openai/" + model_id)
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 4096,
    }
    raw = _http_post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        payload=payload,
    )
    data    = json.loads(raw)
    content = data["choices"][0]["message"]["content"]
    return _parse_model_response(content, "openai/" + model_id)


def review_anthropic(diff_files: list[DiffFile], model_id: str = "claude-opus-4-5") -> ModelReview:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    prompt = _build_review_prompt(diff_files, "anthropic/" + model_id)
    payload = {
        "model": model_id,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    raw = _http_post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        payload=payload,
    )
    data    = json.loads(raw)
    content = data["content"][0]["text"]
    return _parse_model_response(content, "anthropic/" + model_id)


def review_gemini(diff_files: list[DiffFile], model_id: str = "gemini-2.5-flash") -> ModelReview:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    prompt = _build_review_prompt(diff_files, "google/" + model_id)
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_id}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096},
    }
    raw  = _http_post(url, headers={"Content-Type": "application/json"}, payload=payload)
    data = json.loads(raw)
    content = data["candidates"][0]["content"]["parts"][0]["text"]
    return _parse_model_response(content, "google/" + model_id)


# ---------------------------------------------------------------------------
# GitHub Models backend  (OpenAI-compatible, single GITHUB_TOKEN)
# ---------------------------------------------------------------------------

# Models available through the GitHub Models inference endpoint.
# Each is a different model for multi-perspective consensus.
_GITHUB_MODELS: dict[str, str] = {
    "github/gpt-4o":      "gpt-4o",
    "github/gpt-4o-mini": "gpt-4o-mini",
    "github/llama":       "Meta-Llama-3.1-405B-Instruct",
}
# Allowlist of valid CI model keys — derived dynamically from _GITHUB_MODELS to stay in sync.
_ALLOWLIST_GITHUB_MODEL_KEYS: frozenset[str] = frozenset(_GITHUB_MODELS.keys())
# Default model used for CI reviews.  Change via CODE_REVIEW_GITHUB_MODEL env var.
_DEFAULT_GITHUB_MODEL = "github/gpt-4o"
# Default endpoint — override via GITHUB_MODELS_ENDPOINT env var for custom deployments.
_GITHUB_ENDPOINT_DEFAULT = "https://models.inference.ai.azure.com/chat/completions"
# Max output tokens per request.  Override via GITHUB_MODELS_MAX_TOKENS env var.
_GITHUB_MAX_TOKENS_DEFAULT = 2048
_HTTP_TIMEOUT_SECONDS_DEFAULT = 60
_MAX_REVIEWABLE_FILES_DEFAULT = 30


def _http_timeout_seconds() -> int:
    """Return request timeout for AI HTTP calls."""
    try:
        return max(5, int(os.environ.get("CODE_REVIEW_HTTP_TIMEOUT_SECONDS", str(_HTTP_TIMEOUT_SECONDS_DEFAULT))))
    except (TypeError, ValueError):
        return _HTTP_TIMEOUT_SECONDS_DEFAULT


def _max_reviewable_files() -> int:
    """Return maximum number of files to send to model reviews."""
    try:
        return max(1, int(os.environ.get("CODE_REVIEW_MAX_FILES", str(_MAX_REVIEWABLE_FILES_DEFAULT))))
    except (TypeError, ValueError):
        return _MAX_REVIEWABLE_FILES_DEFAULT


def _excluded_review_globs() -> list[str]:
    """Return glob patterns for files intentionally excluded from AI review."""
    defaults = [
        "generated/frontend-app/dist/**",
        "**/node_modules/**",
        "**/.venv/**",
        "**/__pycache__/**",
        "**/*.min.js",
        "**/*.map",
    ]
    extra = os.environ.get("CODE_REVIEW_EXCLUDE_GLOBS", "").strip()
    if not extra:
        return defaults
    parsed = [item.strip() for item in extra.split(",") if item.strip()]
    return defaults + parsed


def _is_excluded_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in _excluded_review_globs():
        if fnmatch.fnmatch(normalized, pattern):
            return True
    return False


def _github_models_endpoint() -> str:
    """Return the GitHub Models inference endpoint, allowing env-var override."""
    return os.environ.get("GITHUB_MODELS_ENDPOINT", _GITHUB_ENDPOINT_DEFAULT)


def _github_max_tokens() -> int:
    """Return the max-tokens limit for GitHub Models requests."""
    try:
        return int(os.environ.get("GITHUB_MODELS_MAX_TOKENS", str(_GITHUB_MAX_TOKENS_DEFAULT)))
    except (TypeError, ValueError):
        return _GITHUB_MAX_TOKENS_DEFAULT


def _validate_github_token(token: str) -> None:
    """Raise RuntimeError with a safe message if *token* looks invalid.

    The token value is never included in any message or log entry.
    """
    if not token or not token.strip():
        raise RuntimeError(
            "GITHUB_TOKEN is not set. "
            "Add it to .env or set the environment variable."
        )


def _call_github_batch(
    batch: list[DiffFile],
    key: str,
    model_id: str,
    token: str,
) -> ModelReview:
    """Send one batch of diff files to the GitHub Models inference API.

    Args:
        batch:    Files to include in this review request.
        key:      Registry key used as the model label in findings (e.g. ``github/gpt-4o``).
        model_id: Actual model identifier accepted by the API.
        token:    GitHub personal access token.  Never logged or echoed.

    Returns:
        A :class:`ModelReview` for this batch.

    Raises:
        RuntimeError: On non-200 HTTP responses, including 413 token-limit errors.
    """
    prompt  = _build_review_prompt(batch, key)
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": _github_max_tokens(),
    }
    # Authorization header constructed at call-site; token never written to
    # logs, tracebacks, or error messages.
    try:
        raw  = _http_post(
            _github_models_endpoint(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            payload=payload,
        )
    except RuntimeError as exc:
        # Re-raise without any chance of the token appearing; _http_post only
        # includes the URL and response body in its message, never headers.
        raise RuntimeError(str(exc)) from None
    data    = json.loads(raw)
    content = data["choices"][0]["message"]["content"]
    return _parse_model_response(content, key)


def _merge_model_review_batches(reviews: list[ModelReview], model_name: str) -> ModelReview:
    """Merge multiple per-batch :class:`ModelReview` objects into one.

    Used when a large diff is split across several API calls.  Findings are
    concatenated; scores are averaged; summaries are joined with a separator.

    Args:
        reviews:    Ordered list of per-batch review results.
        model_name: Registry key shared by all batches (e.g. ``github/gpt-4o``).

    Returns:
        A single :class:`ModelReview` representing the whole diff.
    """
    all_findings = [f for r in reviews for f in r.findings]
    summaries = [
        r.summary for r in reviews
        if r.summary and r.summary != "(model did not produce a structured summary)"
    ]
    avg_score = round(sum(r.score for r in reviews) / len(reviews), 1) if reviews else 5
    return ModelReview(
        model=model_name,
        findings=all_findings,
        summary=" | ".join(summaries) if summaries else "(model did not produce a structured summary)",
        score=int(avg_score),
        raw="\n---\n".join(r.raw for r in reviews),
    )


def _review_github_model(diff_files: list[DiffFile], key: str, model_id: str) -> ModelReview:
    """Review diff files using a model through the GitHub Models inference API.

    Large diffs are automatically split into smaller batches when the API
    returns HTTP 413 (token limit exceeded).  Splitting is iterative (not
    recursive) using an explicit work-queue, which avoids deep call stacks
    for repos with many changed files.

    When a single file is still too large to fit in the context window it is
    skipped with a warning rather than raising an error, so the remaining
    files are still reviewed.

    Batch results are merged via :func:`_merge_model_review_batches`.

    Args:
        diff_files: Files from the git diff to review.
        key:        Registry key / model label (e.g. ``github/gpt-4o``).
        model_id:   Actual model identifier accepted by the inference API.

    Returns:
        A :class:`ModelReview` covering all reviewable files.

    Raises:
        RuntimeError: If ``GITHUB_TOKEN`` is not set, or on non-413 API errors.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    _validate_github_token(token)

    # Iterative work-queue: start with all files, split on 413 token errors.
    # Each element is a list[DiffFile] batch waiting to be reviewed.
    pending: list[list[DiffFile]] = [list(diff_files)]
    batch_reviews: list[ModelReview] = []
    skipped_paths: list[str] = []

    while pending:
        batch = pending.pop()
        if not batch:
            continue
        try:
            batch_reviews.append(_call_github_batch(batch, key, model_id, token))
        except RuntimeError as exc:
            if "HTTP 413" not in str(exc):
                raise
            if len(batch) == 1:
                # Single file is too large — record explicitly so callers know.
                skipped_paths.append(batch[0].path)
                print(
                    f"[warn] {key}: '{batch[0].path}' exceeds context window, skipping",
                    file=sys.stderr,
                )
                continue
            mid = len(batch) // 2
            # Push right half first so left half is processed first (LIFO).
            pending.append(batch[mid:])
            pending.append(batch[:mid])

    if not batch_reviews:
        raise RuntimeError(f"{key}: no batches completed — all files exceeded context window")

    result = batch_reviews[0] if len(batch_reviews) == 1 else _merge_model_review_batches(batch_reviews, key)

    # Append skipped-file notice so callers are explicitly informed.
    if skipped_paths:
        skipped_note = f" [SKIPPED — too large for context: {', '.join(skipped_paths)}]"
        result = ModelReview(
            model=result.model,
            findings=result.findings,
            summary=result.summary + skipped_note,
            score=result.score,
            raw=result.raw,
        )
    return result


def review_github_gpt4o(diff_files: list[DiffFile]) -> ModelReview:
    return _review_github_model(diff_files, "github/gpt-4o", _GITHUB_MODELS["github/gpt-4o"])


def review_github_gpt4o_mini(diff_files: list[DiffFile]) -> ModelReview:
    return _review_github_model(diff_files, "github/gpt-4o-mini", _GITHUB_MODELS["github/gpt-4o-mini"])


def review_github_llama(diff_files: list[DiffFile]) -> ModelReview:
    return _review_github_model(diff_files, "github/llama", _GITHUB_MODELS["github/llama"])


# ---------------------------------------------------------------------------
# Core agent
# ---------------------------------------------------------------------------

class CodeReviewAgent:
    """
    Multi-model expert code reviewer.

    Reviews every file changed in a commit across five dimensions:
    coding standards, security, maintainability, technical debt and
    codebase impact.  Findings agreed on by two or more models are
    elevated to consensus status.  When consensus issues originate inside
    agent source files, targeted improvement notes are written back to the
    offending agents so the defect category cannot recur.

    - This docstring and the companion docs file are regenerated on every
      run so documentation stays current.
    """

    VERSION          = "1.1.0"
    REPORT_FILENAME  = "code-review-report.md"
    DOCS_FILENAME    = "docs/code-review-agent.md"
    REQUEST_FILENAME = "generated/code-review-request.md"

    MODEL_REGISTRY: dict[str, callable] = {
        # GitHub Copilot Models — single GITHUB_TOKEN, multiple models
        "github/gpt-4o":      review_github_gpt4o,
        "github/gpt-4o-mini": review_github_gpt4o_mini,
        "github/llama":       review_github_llama,
        # Direct provider keys (optional fallback)
        "openai":         review_openai,
        "anthropic":      review_anthropic,
        "gemini":         review_gemini,
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_diff(
        self,
        repo_path: Path,
        commit: str,
        base: str,
        diff_file: Path | None = None,
    ) -> list[DiffFile]:
        if diff_file:
            raw = get_diff_from_file(diff_file)
        else:
            raw = get_diff_from_git(repo_path, commit, base)
        parser = DiffParser()
        return parser.parse(raw)

    def _select_reviewable(self, diff_files: list[DiffFile]) -> list[DiffFile]:
        """Apply the same eligibility + truncation filters used by review()."""
        eligible = [
            d for d in diff_files
            if not d.is_deleted and d.content_snippet and not _is_excluded_path(d.path)
        ]
        return eligible[:_max_reviewable_files()]

    def emit_review_request(
        self,
        repo_path: Path,
        commit: str,
        base: str,
        diff_file: Path | None = None,
        out_path: Path | None = None,
    ) -> Path:
        """Write a full-context review request for an interactive chat agent.

        This does NOT call any external model and requires no API keys. It
        captures the diff and review instructions so the chat agent (which has
        full repository context and tooling) can perform the review directly.
        """
        timestamp  = dt.datetime.now(dt.timezone.utc).isoformat()
        diff_files = self.get_diff(repo_path, commit, base, diff_file)
        reviewable = self._select_reviewable(diff_files)
        document   = _build_chat_review_request(reviewable, commit, base, timestamp)

        target = out_path or (repo_path / self.REQUEST_FILENAME)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(document, encoding="utf-8")
        print(f"[info] {len(reviewable)} file(s) captured", file=sys.stderr)
        print(f"[info] chat review request \u2192 {target}", file=sys.stderr)
        return target

    def run_model_reviews(
        self,
        diff_files: list[DiffFile],
        models: list[str],
    ) -> list[ModelReview]:
        reviews: list[ModelReview] = []
        for model_key in models:
            fn = self.MODEL_REGISTRY.get(model_key)
            if fn is None:
                print(f"[warn] unknown model '{model_key}', skipping", file=sys.stderr)
                continue
            try:
                print(f"[info] running {model_key} review …", file=sys.stderr)
                review = fn(diff_files)
                reviews.append(review)
                print(
                    f"[info] {model_key}: score={review.score}/10, "
                    f"findings={len(review.findings)}",
                    file=sys.stderr,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[warn] {model_key} failed: {exc}", file=sys.stderr)
        return reviews

    def find_consensus(self, reviews: list[ModelReview]) -> list[ConsensusIssue]:
        """Elevate findings agreed upon by ≥ 2 models to consensus status."""
        if len(reviews) < 2:
            return []

        # Group findings by normalised key
        key_map: dict[str, list[Finding]] = {}
        for review in reviews:
            for finding in review.findings:
                key = finding.key()
                key_map.setdefault(key, []).append(finding)

        consensus: list[ConsensusIssue] = []
        for key, findings in key_map.items():
            models_agreeing = list({f.model for f in findings})
            if len(models_agreeing) >= 2:
                consensus.append(ConsensusIssue(
                    key=key,
                    findings=findings,
                    agreed_by=models_agreeing,
                ))

        # Sort: critical first
        return sorted(
            consensus,
            key=lambda c: c.canonical.severity.priority(),
            reverse=True,
        )

    def generate_agent_patches(
        self,
        consensus: list[ConsensusIssue],
        repo_path: Path,
    ) -> list[AgentPatch]:
        """For consensus issues in agent files, draft targeted improvement notes."""
        patches: list[AgentPatch] = []
        seen: set[str] = set()

        for issue in consensus:
            f = issue.canonical
            if not f.file.startswith("agents/"):
                continue
            dedup_key = f"{f.file}::{f.dimension.value}::{f.title[:40]}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            target = repo_path / f.file
            if not target.exists():
                continue

            note = (
                f"# CODE-REVIEW-AGENT PATCH NOTE\n"
                f"# Dimension : {f.dimension.value}\n"
                f"# Severity  : {f.severity.value}\n"
                f"# Issue     : {f.title}\n"
                f"# Agreed by : {', '.join(issue.agreed_by)}\n"
                f"# Suggestion: {f.suggestion}\n"
            )
            patches.append(AgentPatch(
                target_agent=f.file,
                issue_title=f.title,
                dimension=f.dimension,
                severity=f.severity,
                suggestion=note,
            ))

            # Append the note to the agent file so developers see it inline
            existing = target.read_text(encoding="utf-8")
            marker   = f"# CODE-REVIEW NOTE: {f.title[:40]}"
            if marker not in existing:
                with target.open("a", encoding="utf-8") as fh:
                    fh.write(f"\n\n{note}")

        return patches

    def review(
        self,
        repo_path: Path,
        commit: str,
        base: str,
        models: list[str],
        diff_file: Path | None = None,
        write_report: bool = True,
        patch_agents: bool = True,
    ) -> ReviewResult:
        timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
        print(f"[info] code-review-agent v{self.VERSION} | {timestamp}", file=sys.stderr)

        diff_files   = self.get_diff(repo_path, commit, base, diff_file)
        eligible = [
            d for d in diff_files
            if not d.is_deleted and d.content_snippet and not _is_excluded_path(d.path)
        ]
        excluded_count = len(diff_files) - len(eligible)
        max_files = _max_reviewable_files()
        reviewable = eligible[:max_files]
        truncated_count = max(0, len(eligible) - len(reviewable))

        print(f"[info] {len(reviewable)} files to review", file=sys.stderr)
        if excluded_count:
            print(f"[info] excluded {excluded_count} file(s) by path filters", file=sys.stderr)
        if truncated_count:
            print(
                f"[warn] review scope truncated to {max_files} file(s); "
                f"{truncated_count} additional file(s) skipped",
                file=sys.stderr,
            )

        if not reviewable:
            print("[warn] no reviewable content in diff", file=sys.stderr)

        model_reviews = self.run_model_reviews(reviewable, models)
        consensus     = self.find_consensus(model_reviews)
        agent_patches: list[AgentPatch] = []

        if patch_agents and consensus:
            agent_patches = self.generate_agent_patches(consensus, repo_path)
            if agent_patches:
                print(
                    f"[info] {len(agent_patches)} agent patch note(s) written",
                    file=sys.stderr,
                )

        result = ReviewResult(
            commit=commit,
            base=base,
            repo_path=str(repo_path),
            timestamp=timestamp,
            model_reviews=model_reviews,
            consensus=consensus,
            agent_patches=agent_patches,
            files_reviewed=[d.path for d in reviewable],
        )

        if write_report:
            report_path = repo_path / self.REPORT_FILENAME
            report_path.write_text(self._build_report(result), encoding="utf-8")
            print(f"[info] report → {report_path}", file=sys.stderr)

        return result

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def _build_report(self, result: ReviewResult) -> str:
        lines: list[str] = []
        a = lines.append

        a(f"# Code Review Report")
        a(f"")
        a(f"| Field | Value |")
        a(f"|---|---|")
        a(f"| Commit | `{result.commit}` |")
        a(f"| Base | `{result.base}` |")
        a(f"| Timestamp | {result.timestamp} |")
        a(f"| Overall quality score | **{result.overall_score()}/10** |")
        a(f"| Files reviewed | {len(result.files_reviewed)} |")
        a(f"| Models used | {', '.join(r.model for r in result.model_reviews)} |")
        a(f"| Total findings | {sum(len(r.findings) for r in result.model_reviews)} |")
        a(f"| Consensus issues | {len(result.consensus)} |")
        a(f"| Agent patches applied | {len(result.agent_patches)} |")
        a("")

        # Files
        a("## Files reviewed")
        a("")
        for f in result.files_reviewed:
            a(f"- `{f}`")
        a("")

        # Consensus issues (highest priority)
        if result.consensus:
            a("## Consensus issues (agreed by ≥ 2 models)")
            a("")
            a("> These findings were independently identified by multiple AI models and should be treated as highest priority.")
            a("")
            for ci in result.consensus:
                f = ci.canonical
                a(f"### {f.severity.emoji()} `{f.severity.value.upper()}` — {f.title}")
                a(f"")
                a(f"- **File**: `{f.file}`{(' line ' + str(f.line)) if f.line else ''}")
                a(f"- **Dimension**: {f.dimension.value}")
                a(f"- **Agreed by**: {', '.join(ci.agreed_by)}")
                a(f"")
                a(f"**Detail**: {f.detail}")
                a(f"")
                a(f"**Suggestion**: {f.suggestion}")
                a("")

        # Per-model summaries
        a("## Per-model summaries")
        a("")
        for review in result.model_reviews:
            a(f"### {review.model} (score: {review.score}/10)")
            a("")
            a(review.summary)
            a("")

        # All findings by severity
        findings_by_sev = result.findings_by_severity()
        for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
            items = findings_by_sev[sev]
            if not items:
                continue
            a(f"## {sev.emoji()} {sev.value.capitalize()} findings ({len(items)})")
            a("")
            for f in items:
                a(f"### [{f.model}] {f.title}")
                a(f"- **File**: `{f.file}`{(' line ' + str(f.line)) if f.line else ''}")
                a(f"- **Dimension**: `{f.dimension.value}`")
                a(f"")
                a(f"{f.detail}")
                a(f"")
                a(f"> **Fix**: {f.suggestion}")
                a("")

        # Agent patches
        if result.agent_patches:
            a("## Agent patches applied")
            a("")
            a("The following improvement notes were written back to agent source files:")
            a("")
            for patch in result.agent_patches:
                a(f"- `{patch.target_agent}` — **{patch.severity.value}** `{patch.issue_title}`")
            a("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Self-documentation
    # ------------------------------------------------------------------

    def self_documentation_markdown(self) -> str:
        return "\n".join([
            "# Code Review Agent",
            "",
            "## Purpose",
            "",
            "`agents/code_review_agent.py` performs expert, multi-model AI code review on every",
            "git check-in.  It analyses changed files across five dimensions and aggregates findings",
            "from multiple AI models to produce objective, consensus-driven feedback.",
            "",
            "## Recommended setup — GitHub Copilot Models",
            "",
            "A single `GITHUB_TOKEN` (available to all GitHub Copilot subscribers) unlocks three",
            "models through the GitHub Models inference endpoint — ideal for",
            "multi-model consensus without needing separate provider API keys.",
            "",
            "Add to `.env` in the repo root:",
            "",
            "```",
            "GITHUB_TOKEN=ghp_...",
            "```",
            "",
            "| Model key | Model | Notes |",
            "|---|---|---|",
            "| `github/gpt-4o` | GPT-4o | Full-capability OpenAI model |",
            "| `github/gpt-4o-mini` | GPT-4o Mini | Faster, complementary perspective |",
            "| `github/llama` | Meta Llama 3.1 405B | Open-weight alternative architecture |",
            "",
            "## Review dimensions",
            "",
            "| Dimension | What is checked |",
            "|---|---|",
            "| `coding_standards` | Style, naming, idioms, structure for the language |",
            "| `security` | OWASP Top 10, secret leakage, injection, auth/authz flaws |",
            "| `maintainability` | Complexity, coupling, readability, test coverage |",
            "| `technical_debt` | Shortcuts, TODOs, dead code, duplication |",
            "| `codebase_impact` | API surface changes, breaking contracts, dep graph effects |",
            "",
            "## Multi-model objectivity",
            "",
            "Findings flagged by **≥ 2 models** are promoted to *consensus* status and receive",
            "the highest remediation priority in the report.",
            "",
            "## Alternative backends (optional)",
            "",
            "Direct provider API keys are also supported:",
            "",
            "| Key | Model | Env var |",
            "|---|---|---|",
            "| `openai` | GPT-4o | `OPENAI_API_KEY` |",
            "| `anthropic` | Claude Opus | `ANTHROPIC_API_KEY` |",
            "| `gemini` | Gemini 2.5 Flash | `GEMINI_API_KEY` |",
            "",
            "## Agent self-improvement",
            "",
            "When a consensus issue originates from a file inside `agents/`, the agent appends",
            "a structured patch note directly to the offending agent file so future iterations",
            "of that agent are aware of the recurring defect category.",
            "",
            "## Usage",
            "",
            "```bash",
            "# Review HEAD against its parent (uses all available models automatically)",
            "python agents/code_review_agent.py --commit HEAD",
            "",
            "# Review a specific commit against a branch",
            "python agents/code_review_agent.py --commit abc123 --base main",
            "",
            "# Review from a patch file",
            "python agents/code_review_agent.py --diff-file /tmp/my.patch",
            "",
            "# Use only specific models",
            "python agents/code_review_agent.py --commit HEAD --models github/gpt-4o github/gpt-4o-mini",
            "",
            "# Regenerate this documentation",
            "python agents/code_review_agent.py --commit HEAD --update-docs",
            "```",
            "",
            "## Options",
            "",
            "| Flag | Default | Description |",
            "|---|---|---|",
            "| `--commit` | `HEAD` | Commit SHA or ref to review |",
            "| `--base` | `HEAD~1` | Base ref for the diff |",
            "| `--diff-file` | — | Read diff from a file instead of git |",
            "| `--repo` | `.` | Path to the git repository |",
            "| `--models` | all available | Space-separated model keys to use |",
            "| `--no-patch-agents` | flag | Disable automatic agent patching |",
            "| `--no-report` | flag | Skip writing the report file |",
            "| `--update-docs` | flag | Regenerate docs/code-review-agent.md |",
            "",
            "## Output",
            "",
            "- `code-review-report.md` — full report written to repo root",
            "- Inline patch notes appended to agent source files when consensus issues are found",
            "",
            "## Environment variables",
            "",
            "```",
            "GITHUB_TOKEN        — recommended: unlocks github/gpt-4o, github/gpt-4o-mini, github/llama",
            "OPENAI_API_KEY      — optional: direct OpenAI access",
            "ANTHROPIC_API_KEY   — optional: direct Anthropic access",
            "GEMINI_API_KEY      — optional: direct Google Gemini access",
            "```",
            "",
            "## Notes",
            "",
            "- Uses Python standard library only (no third-party dependencies).",
            "- All AI calls use urllib with a 120-second timeout.",
            "- Partial results are returned if a model fails.",
            "- Diff content per file is capped at 8 000 characters to stay within model context limits.",
            f"- Agent version: {self.VERSION}",
            "",
        ])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _default_github_model() -> str:
    """Return the single GitHub model used for CI reviews.

    Override by setting CODE_REVIEW_GITHUB_MODEL to any key in
    ``_ALLOWED_GITHUB_MODEL_KEYS``.  Invalid values are rejected with a
    warning and fall back to ``_DEFAULT_GITHUB_MODEL``.

    github/gpt-4o-mini and github/llama are available via ``--models`` on
    the CLI but excluded from the default CI path because they exhibited
    inconsistent response latency on large diffs, causing the CI gate to
    stall.  The env-var override lets teams opt in to those models when
    latency is acceptable.
    """
    raw = os.environ.get("CODE_REVIEW_GITHUB_MODEL", _DEFAULT_GITHUB_MODEL).strip()
    # Step 1: Reject values that contain characters outside the allowed set (a-z, A-Z, 0-9, /, -).
    # This guards against injection attempts before the allowlist lookup.
    if not re.fullmatch(r"[a-zA-Z0-9/_-]+", raw):
        # SAFETY: do not include raw value in this message to prevent log exposure.
        print(
            "[warn] CODE_REVIEW_GITHUB_MODEL contains disallowed characters; "
            f"falling back to {_DEFAULT_GITHUB_MODEL}",
            file=sys.stderr,
        )
        return _DEFAULT_GITHUB_MODEL
    # Step 2: Allowlist-validate against known model keys; never echo the raw value.
    if raw not in _ALLOWLIST_GITHUB_MODEL_KEYS:
        # SAFETY: do not include raw value in this message to prevent log exposure.
        print(
            "[warn] CODE_REVIEW_GITHUB_MODEL is not a recognised GitHub model key; "
            f"falling back to {_DEFAULT_GITHUB_MODEL}",
            file=sys.stderr,
        )
        return _DEFAULT_GITHUB_MODEL
    return raw


def _available_models() -> list[str]:
    """Return model keys for which credentials are configured.

    Uses a single GitHub model by default (github/gpt-4o or the value of
    CODE_REVIEW_GITHUB_MODEL) to keep CI review latency predictable.
    Additional models can be requested explicitly via --models on the CLI.
    Credentials are validated at call-site inside each model function;
    their values are never included in log output.
    """
    available = []
    # GitHub Models — single model by default for consistent CI latency.
    # Presence of GITHUB_TOKEN is checked here; its value is never logged.
    if os.environ.get("GITHUB_TOKEN"):
        available.append(_default_github_model())
    # Direct provider keys as optional supplements.
    if os.environ.get("OPENAI_API_KEY"):
        available.append("openai")
    if os.environ.get("ANTHROPIC_API_KEY"):
        available.append("anthropic")
    if os.environ.get("GEMINI_API_KEY"):
        available.append("gemini")
    return available


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Expert multi-model code review agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--commit",        default="HEAD",  help="Commit SHA or ref to review (default: HEAD)")
    parser.add_argument("--base",          default=None,    help="Base ref for the diff (default: <commit>~1)")
    parser.add_argument("--diff-file",     default=None,    help="Read diff from a file instead of git")
    parser.add_argument("--repo",          default=".",     help="Path to the git repository (default: .)")
    parser.add_argument("--models",        nargs="+",       help="Model keys to use: openai anthropic gemini")
    parser.add_argument("--no-patch-agents", action="store_true", help="Disable automatic agent patching")
    parser.add_argument("--no-report",     action="store_true",   help="Skip writing the report file")
    parser.add_argument("--update-docs",   action="store_true",   help="Regenerate docs/code-review-agent.md")
    parser.add_argument(
        "--emit-prompt",
        action="store_true",
        help="Emit a full-context review request for an interactive chat agent "
             "instead of calling external models (no API key required)",
    )
    parser.add_argument("--out", default=None, help="Output path for --emit-prompt (default: generated/code-review-request.md)")
    args = parser.parse_args()

    repo_path = Path(args.repo).resolve()
    _load_dotenv(repo_path)   # load .env before key checks

    commit    = args.commit
    base      = args.base or f"{commit}~1"
    diff_file = Path(args.diff_file) if args.diff_file else None
    models    = args.models or _available_models()

    if args.emit_prompt:
        agent = CodeReviewAgent()
        target = agent.emit_review_request(
            repo_path=repo_path,
            commit=commit,
            base=base,
            diff_file=diff_file,
            out_path=Path(args.out).resolve() if args.out else None,
        )
        print(f"\nChat review request ready")
        print(f"{'─' * 40}")
        print(f"Request file : {target}")
        print("Next step    : open this file in chat and ask for the review.")
        return 0

    if not models:
        print(
            "[error] No AI credentials found.  Set at least one of:\n"
            "  GITHUB_TOKEN       — recommended (unlocks GPT-4o, Claude, Llama via GitHub Copilot)\n"
            "  OPENAI_API_KEY     — direct OpenAI access\n"
            "  ANTHROPIC_API_KEY  — direct Anthropic access\n"
            "  GEMINI_API_KEY     — direct Google Gemini access",
            file=sys.stderr,
        )
        return 1

    agent  = CodeReviewAgent()
    result = agent.review(
        repo_path=repo_path,
        commit=commit,
        base=base,
        models=models,
        diff_file=diff_file,
        write_report=not args.no_report,
        patch_agents=not args.no_patch_agents,
    )

    if args.update_docs:
        docs_path = repo_path / agent.DOCS_FILENAME
        docs_path.parent.mkdir(parents=True, exist_ok=True)
        docs_path.write_text(agent.self_documentation_markdown(), encoding="utf-8")
        print(f"[info] docs updated → {docs_path}", file=sys.stderr)

    # Print terse human-readable summary to stdout
    print(f"\nCode Review Complete")
    print(f"{'─' * 40}")
    print(f"Overall score   : {result.overall_score()}/10")
    print(f"Files reviewed  : {len(result.files_reviewed)}")
    print(f"Models used     : {', '.join(r.model for r in result.model_reviews)}")
    total = sum(len(r.findings) for r in result.model_reviews)
    print(f"Total findings  : {total}")
    print(f"Consensus issues: {len(result.consensus)}")
    if result.agent_patches:
        print(f"Agent patches   : {len(result.agent_patches)}")

    by_sev = result.findings_by_severity()
    for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM]:
        count = len(by_sev[sev])
        if count:
            print(f"  {sev.emoji()} {sev.value:<10}: {count}")

    return 1 if by_sev[Severity.CRITICAL] else 0


if __name__ == "__main__":
    raise SystemExit(main())


# CODE-REVIEW-AGENT PATCH NOTE
# Dimension : security
# Severity  : high
# Issue     : Potential secret leakage
# Agreed by : github/llama, github/gpt-4o-mini
# Suggestion: Implement a more secure error handling mechanism that does not expose sensitive information and ensure the token is validated before use.


# CODE-REVIEW-AGENT PATCH NOTE
# Dimension : security
# Severity  : high
# Issue     : Potential secret leakage
# Agreed by : github/gpt-4o-mini, github/llama
# Suggestion: Implement a more secure error handling mechanism that does not expose sensitive information and ensure the token is validated before use.


# CODE-REVIEW-AGENT PATCH NOTE
# Dimension : security
# Severity  : high
# Issue     : Potential secret leakage
# Agreed by : github/llama, github/gpt-4o-mini
# Suggestion: Implement stricter validation for the GitHub token and ensure that it is never logged or printed in any form.
