from __future__ import annotations

"""Tests for code_review_agent.py"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.code_review_agent import (
    AgentPatch,
    CodeReviewAgent,
    ConsensusIssue,
    DiffFile,
    DiffParser,
    Dimension,
    Finding,
    ModelReview,
    ReviewResult,
    Severity,
    _parse_model_response,
    _review_github_model,
    review_github_gpt4o,
    review_github_gpt4o_mini,
    review_github_llama,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_DIFF = """\
diff --git a/agents/example_agent.py b/agents/example_agent.py
index abc1234..def5678 100644
--- a/agents/example_agent.py
+++ b/agents/example_agent.py
@@ -1,5 +1,10 @@
+import os
+
 def run():
-    pass
+    secret = "hardcoded-api-key-123"
+    password = "hunter2"
+    query = f"SELECT * FROM users WHERE id = {input()}"
+    return secret
"""

SAMPLE_DIFF_NO_AGENTS = """\
diff --git a/src/utils.py b/src/utils.py
index abc1234..def5678 100644
--- a/src/utils.py
+++ b/src/utils.py
@@ -1,3 +1,6 @@
+def helper():
+    x = 1+1
+    return x
"""

FINDING_SECURITY = {
    "dimension": "security",
    "severity": "critical",
    "file": "agents/example_agent.py",
    "line": 4,
    "title": "Hardcoded secret in source",
    "detail": "API key stored in plain text.",
    "suggestion": "Use environment variables or a secrets manager.",
}

FINDING_DEBT = {
    "dimension": "technical_debt",
    "severity": "medium",
    "file": "agents/example_agent.py",
    "line": None,
    "title": "Dead code: pass statement replaced but not removed",
    "detail": "The pass was replaced but left a comment smell.",
    "suggestion": "Remove dead code.",
}

SUMMARY_BLOCK = {
    "summary": "This code has critical security issues.",
    "score": 3,
}


def _make_raw_response(*finding_dicts, summary=None) -> str:
    parts = []
    for d in finding_dicts:
        parts.append(f"```json\n{json.dumps(d)}\n```")
    summary_obj = summary or SUMMARY_BLOCK
    parts.append(f"```json\n{json.dumps(summary_obj)}\n```")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# DiffParser tests
# ---------------------------------------------------------------------------

class TestDiffParser:
    def test_parses_single_file(self):
        parser = DiffParser()
        files  = parser.parse(SAMPLE_DIFF)
        assert len(files) == 1
        assert files[0].path == "agents/example_agent.py"

    def test_detects_new_file(self):
        diff = (
            "diff --git a/new_file.py b/new_file.py\n"
            "new file mode 100644\n"
            "index 0000000..abc1234\n"
            "--- /dev/null\n"
            "+++ b/new_file.py\n"
            "@@ -0,0 +1 @@\n"
            "+print('hello')\n"
        )
        files = DiffParser().parse(diff)
        assert files[0].is_new is True

    def test_detects_deleted_file(self):
        diff = (
            "diff --git a/old.py b/old.py\n"
            "deleted file mode 100644\n"
            "index abc1234..0000000\n"
            "--- a/old.py\n"
            "+++ /dev/null\n"
        )
        files = DiffParser().parse(diff)
        assert files[0].is_deleted is True

    def test_no_hunks_on_empty_body(self):
        diff = "diff --git a/a.py b/a.py\nindex abc..def 100644\n"
        files = DiffParser().parse(diff)
        assert files[0].hunks == []

    def test_extension(self):
        files = DiffParser().parse(SAMPLE_DIFF)
        assert files[0].extension == ".py"

    def test_is_agent_true(self):
        files = DiffParser().parse(SAMPLE_DIFF)
        assert files[0].is_agent is True

    def test_is_agent_false(self):
        files = DiffParser().parse(SAMPLE_DIFF_NO_AGENTS)
        assert files[0].is_agent is False

    def test_content_snippet_non_empty(self):
        files = DiffParser().parse(SAMPLE_DIFF)
        assert files[0].content_snippet != ""

    def test_parse_empty_diff(self):
        files = DiffParser().parse("")
        assert files == []

    def test_parse_multiple_files(self):
        diff = SAMPLE_DIFF + "\n" + SAMPLE_DIFF_NO_AGENTS
        files = DiffParser().parse(diff)
        assert len(files) == 2


# ---------------------------------------------------------------------------
# _parse_model_response tests
# ---------------------------------------------------------------------------

class TestParseModelResponse:
    def test_parses_finding_and_summary(self):
        raw    = _make_raw_response(FINDING_SECURITY)
        review = _parse_model_response(raw, "test-model")
        assert len(review.findings) == 1
        assert review.score == 3
        assert "critical security" in review.summary

    def test_severity_parsed(self):
        raw    = _make_raw_response(FINDING_SECURITY)
        review = _parse_model_response(raw, "test-model")
        assert review.findings[0].severity == Severity.CRITICAL

    def test_dimension_parsed(self):
        raw    = _make_raw_response(FINDING_SECURITY)
        review = _parse_model_response(raw, "test-model")
        assert review.findings[0].dimension == Dimension.SECURITY

    def test_line_none(self):
        raw    = _make_raw_response(FINDING_DEBT)
        review = _parse_model_response(raw, "test-model")
        assert review.findings[0].line is None

    def test_line_integer(self):
        raw    = _make_raw_response(FINDING_SECURITY)
        review = _parse_model_response(raw, "test-model")
        assert review.findings[0].line == 4

    def test_score_clamped(self):
        raw    = _make_raw_response(summary={"summary": "ok", "score": 999})
        review = _parse_model_response(raw, "test-model")
        assert review.score == 10

    def test_unknown_dimension_defaults(self):
        finding = dict(FINDING_SECURITY, dimension="nonsense")
        raw     = _make_raw_response(finding)
        review  = _parse_model_response(raw, "test-model")
        assert review.findings[0].dimension == Dimension.MAINTAINABILITY

    def test_unknown_severity_defaults(self):
        finding = dict(FINDING_SECURITY, severity="ultramax")
        raw     = _make_raw_response(finding)
        review  = _parse_model_response(raw, "test-model")
        assert review.findings[0].severity == Severity.MEDIUM

    def test_no_json_blocks_returns_empty_findings(self):
        review = _parse_model_response("No JSON here at all.", "test-model")
        assert review.findings == []

    def test_model_name_attached(self):
        raw    = _make_raw_response(FINDING_SECURITY)
        review = _parse_model_response(raw, "my-model")
        assert review.findings[0].model == "my-model"

    def test_multiple_findings(self):
        raw    = _make_raw_response(FINDING_SECURITY, FINDING_DEBT)
        review = _parse_model_response(raw, "m")
        assert len(review.findings) == 2

    def test_malformed_json_skipped(self):
        raw = "```json\n{bad json\n```\n```json\n" + json.dumps(SUMMARY_BLOCK) + "\n```"
        review = _parse_model_response(raw, "m")
        assert review.findings == []
        assert review.score == 3


# ---------------------------------------------------------------------------
# Severity / Dimension helpers
# ---------------------------------------------------------------------------

class TestSeverity:
    def test_emoji_critical(self):
        assert Severity.CRITICAL.emoji() == "🔴"

    def test_priority_ordering(self):
        assert Severity.CRITICAL.priority() > Severity.HIGH.priority()
        assert Severity.HIGH.priority()     > Severity.MEDIUM.priority()
        assert Severity.MEDIUM.priority()   > Severity.LOW.priority()
        assert Severity.LOW.priority()      > Severity.INFO.priority()

    def test_finding_key_stable(self):
        # Same dimension, severity, file, and title → identical key regardless of other fields
        f1 = Finding(Dimension.SECURITY, Severity.HIGH, "a.py", 1, "Hardcoded secret", "d1", "s1", "openai")
        f2 = Finding(Dimension.SECURITY, Severity.HIGH, "a.py", 9, "Hardcoded secret", "d2", "s2", "anthropic")
        assert f1.key() == f2.key()


# ---------------------------------------------------------------------------
# ConsensusIssue tests
# ---------------------------------------------------------------------------

class TestConsensusIssue:
    def _make_finding(self, model: str, severity: Severity = Severity.HIGH) -> Finding:
        return Finding(Dimension.SECURITY, severity, "agents/foo.py", 1, "Hardcoded secret", "d", "s", model)

    def test_canonical_is_highest_severity(self):
        f_high = self._make_finding("openai",    Severity.HIGH)
        f_crit = self._make_finding("anthropic", Severity.CRITICAL)
        ci = ConsensusIssue(key="k", findings=[f_high, f_crit], agreed_by=["openai", "anthropic"])
        assert ci.canonical.severity == Severity.CRITICAL

    def test_is_agent_issue_true(self):
        f = self._make_finding("openai")
        ci = ConsensusIssue(key="k", findings=[f], agreed_by=["openai"])
        assert ci.is_agent_issue is True

    def test_is_agent_issue_false(self):
        f = Finding(Dimension.SECURITY, Severity.HIGH, "src/utils.py", 1, "X", "d", "s", "m")
        ci = ConsensusIssue(key="k", findings=[f], agreed_by=["m"])
        assert ci.is_agent_issue is False


# ---------------------------------------------------------------------------
# CodeReviewAgent unit tests
# ---------------------------------------------------------------------------

class TestCodeReviewAgentFindConsensus:
    def _review(self, model: str, findings: list[Finding]) -> ModelReview:
        return ModelReview(model=model, findings=findings, summary="", score=7, raw="")

    def _finding(self, model: str, title: str = "Issue A") -> Finding:
        return Finding(Dimension.SECURITY, Severity.HIGH, "a.py", 1, title, "d", "s", model)

    def test_consensus_requires_two_models(self):
        agent = CodeReviewAgent()
        f     = self._finding("openai")
        r     = self._review("openai", [f])
        # Only one model → no consensus possible
        result = agent.find_consensus([r])
        assert result == []

    def test_consensus_detected(self):
        agent = CodeReviewAgent()
        f1    = self._finding("openai")
        f2    = self._finding("anthropic")
        r1    = self._review("openai",    [f1])
        r2    = self._review("anthropic", [f2])
        result = agent.find_consensus([r1, r2])
        assert len(result) == 1
        assert set(result[0].agreed_by) == {"openai", "anthropic"}

    def test_no_consensus_when_different_issues(self):
        agent = CodeReviewAgent()
        f1    = self._finding("openai",    "Issue A")
        f2    = self._finding("anthropic", "Issue B — totally different")
        r1    = self._review("openai",    [f1])
        r2    = self._review("anthropic", [f2])
        # Different titles → different keys → no consensus
        result = agent.find_consensus([r1, r2])
        assert result == []

    def test_consensus_sorted_by_severity(self):
        agent = CodeReviewAgent()

        def finding(model: str, sev: Severity, title: str) -> Finding:
            return Finding(Dimension.SECURITY, sev, "a.py", 1, title, "d", "s", model)

        low_f1  = finding("openai",    Severity.LOW,      "Low issue here")
        low_f2  = finding("anthropic", Severity.LOW,      "Low issue here")
        crit_f1 = finding("openai",    Severity.CRITICAL, "Critical problem!")
        crit_f2 = finding("anthropic", Severity.CRITICAL, "Critical problem!")

        r1 = self._review("openai",    [low_f1, crit_f1])
        r2 = self._review("anthropic", [low_f2, crit_f2])

        result = agent.find_consensus([r1, r2])
        assert len(result) == 2
        assert result[0].canonical.severity == Severity.CRITICAL

    def test_three_models_all_agree(self):
        agent = CodeReviewAgent()
        f1    = self._finding("openai")
        f2    = self._finding("anthropic")
        f3    = self._finding("gemini")
        r1    = self._review("openai",    [f1])
        r2    = self._review("anthropic", [f2])
        r3    = self._review("gemini",    [f3])
        result = agent.find_consensus([r1, r2, r3])
        assert len(result) == 1
        assert len(result[0].agreed_by) == 3


# ---------------------------------------------------------------------------
# ReviewResult helpers
# ---------------------------------------------------------------------------

class TestReviewResult:
    def _result(self, scores: list[int]) -> ReviewResult:
        reviews = [
            ModelReview(model=f"m{i}", findings=[], summary="", score=s, raw="")
            for i, s in enumerate(scores)
        ]
        return ReviewResult(
            commit="abc",
            base="HEAD~1",
            repo_path=".",
            timestamp="2026-01-01T00:00:00Z",
            model_reviews=reviews,
            consensus=[],
            agent_patches=[],
            files_reviewed=[],
        )

    def test_overall_score_average(self):
        r = self._result([8, 6])
        assert r.overall_score() == 7.0

    def test_overall_score_empty(self):
        r = self._result([])
        assert r.overall_score() == 0.0

    def test_findings_by_severity_keys(self):
        r = self._result([7])
        by_sev = r.findings_by_severity()
        assert set(by_sev.keys()) == set(Severity)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

class TestReportGeneration:
    def test_report_contains_score(self):
        agent  = CodeReviewAgent()
        result = ReviewResult(
            commit="abc123",
            base="HEAD~1",
            repo_path=".",
            timestamp="2026-01-01T00:00:00Z",
            model_reviews=[ModelReview("openai", [], "Looks good.", 9, "")],
            consensus=[],
            agent_patches=[],
            files_reviewed=["src/main.py"],
        )
        report = agent._build_report(result)
        assert "9/10" in report
        assert "abc123" in report
        assert "src/main.py" in report

    def test_consensus_section_present_when_issues(self):
        agent = CodeReviewAgent()
        f     = Finding(Dimension.SECURITY, Severity.CRITICAL, "a.py", 1, "Critical bug", "d", "s", "openai")
        ci    = ConsensusIssue(key="k", findings=[f], agreed_by=["openai", "anthropic"])
        result = ReviewResult(
            commit="abc",
            base="HEAD~1",
            repo_path=".",
            timestamp="t",
            model_reviews=[],
            consensus=[ci],
            agent_patches=[],
            files_reviewed=[],
        )
        report = agent._build_report(result)
        assert "Consensus issues" in report
        assert "Critical bug" in report

    def test_no_consensus_section_when_none(self):
        agent  = CodeReviewAgent()
        result = ReviewResult("a", "b", ".", "t", [], [], [], [])
        report = agent._build_report(result)
        # Section heading is always present; with no issues the list should be empty
        assert "Consensus issues" in report
        assert result.consensus == []


# ---------------------------------------------------------------------------
# Self-documentation
# ---------------------------------------------------------------------------

class TestSelfDocumentation:
    def test_docs_contain_version(self):
        agent = CodeReviewAgent()
        docs  = agent.self_documentation_markdown()
        assert CodeReviewAgent.VERSION in docs

    def test_docs_contain_all_dimensions(self):
        agent = CodeReviewAgent()
        docs  = agent.self_documentation_markdown()
        for dim in Dimension:
            assert dim.value in docs

    def test_docs_contain_all_model_keys(self):
        agent = CodeReviewAgent()
        docs  = agent.self_documentation_markdown()
        for key in ("openai", "anthropic", "gemini"):
            assert key in docs

    def test_docs_contain_usage_example(self):
        docs = CodeReviewAgent().self_documentation_markdown()
        assert "code_review_agent.py" in docs

    def test_docs_mention_github_token(self):
        docs = CodeReviewAgent().self_documentation_markdown()
        assert "GITHUB_TOKEN" in docs

    def test_docs_mention_github_models(self):
        docs = CodeReviewAgent().self_documentation_markdown()
        for key in ("github/gpt-4o", "github/gpt-4o-mini", "github/llama"):
            assert key in docs


# ---------------------------------------------------------------------------
# GitHub Models backend tests
# ---------------------------------------------------------------------------

class TestGitHubModelsBackend:
    def _make_diff_files(self) -> list[DiffFile]:
        return DiffParser().parse(SAMPLE_DIFF)

    def test_github_model_raises_without_token(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
            _review_github_model(self._make_diff_files(), "github/gpt-4o", "gpt-4o")

    def test_github_gpt4o_raises_without_token(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
            review_github_gpt4o(self._make_diff_files())

    def test_github_gpt4o_mini_raises_without_token(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
            review_github_gpt4o_mini(self._make_diff_files())

    def test_github_llama_raises_without_token(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
            review_github_llama(self._make_diff_files())

    def test_github_models_in_registry(self):
        registry = CodeReviewAgent.MODEL_REGISTRY
        assert "github/gpt-4o" in registry
        assert "github/gpt-4o-mini" in registry
        assert "github/llama" in registry

    def test_github_models_detected_when_token_set(self, monkeypatch):
        from agents.code_review_agent import _available_models
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("CODE_REVIEW_GITHUB_MODEL", raising=False)
        models = _available_models()
        assert "github/gpt-4o" in models
        # gpt-4o-mini and llama no longer appear in the default list
        assert "github/gpt-4o-mini" not in models
        assert "github/llama" not in models

    # ------------------------------------------------------------------
    # _default_github_model behaviour
    # ------------------------------------------------------------------

    def test_default_github_model_returns_default(self, monkeypatch):
        from agents.code_review_agent import _DEFAULT_GITHUB_MODEL, _default_github_model
        monkeypatch.delenv("CODE_REVIEW_GITHUB_MODEL", raising=False)
        assert _default_github_model() == _DEFAULT_GITHUB_MODEL

    def test_default_github_model_env_override_valid(self, monkeypatch):
        from agents.code_review_agent import _default_github_model
        monkeypatch.setenv("CODE_REVIEW_GITHUB_MODEL", "github/gpt-4o-mini")
        assert _default_github_model() == "github/gpt-4o-mini"

    def test_default_github_model_env_override_invalid_falls_back(self, monkeypatch, capsys):
        from agents.code_review_agent import _DEFAULT_GITHUB_MODEL, _default_github_model
        monkeypatch.setenv("CODE_REVIEW_GITHUB_MODEL", "not-a-real-model")
        result = _default_github_model()
        assert result == _DEFAULT_GITHUB_MODEL
        captured = capsys.readouterr()
        # Warning must not include the raw env-var value to avoid info leakage
        assert "not-a-real-model" not in captured.err
        assert "warn" in captured.err

    def test_default_github_model_env_override_empty_falls_back(self, monkeypatch):
        from agents.code_review_agent import _DEFAULT_GITHUB_MODEL, _default_github_model
        monkeypatch.setenv("CODE_REVIEW_GITHUB_MODEL", "   ")
        assert _default_github_model() == _DEFAULT_GITHUB_MODEL

    def test_default_github_model_special_chars_fall_back(self, monkeypatch):
        from agents.code_review_agent import _DEFAULT_GITHUB_MODEL, _default_github_model
        monkeypatch.setenv("CODE_REVIEW_GITHUB_MODEL", "github/gpt-4o; rm -rf /")
        assert _default_github_model() == _DEFAULT_GITHUB_MODEL

    def test_default_github_model_very_long_value_falls_back(self, monkeypatch):
        from agents.code_review_agent import _DEFAULT_GITHUB_MODEL, _default_github_model
        monkeypatch.setenv("CODE_REVIEW_GITHUB_MODEL", "x" * 500)
        assert _default_github_model() == _DEFAULT_GITHUB_MODEL

    def test_default_github_model_warning_never_echoes_value(self, monkeypatch, capsys):
        from agents.code_review_agent import _default_github_model
        secret_value = "definitely-not-a-model-ghp_secret123"
        monkeypatch.setenv("CODE_REVIEW_GITHUB_MODEL", secret_value)
        _default_github_model()
        captured = capsys.readouterr()
        assert secret_value not in captured.err
        assert secret_value not in captured.out

    def test_github_models_not_detected_without_token(self, monkeypatch):
        from agents.code_review_agent import _available_models
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        models = _available_models()
        assert not any(m.startswith("github/") for m in models)

    def test_github_models_take_priority_over_direct_keys(self, monkeypatch):
        from agents.code_review_agent import _available_models
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        models = _available_models()
        # github models should appear before openai
        github_indices = [i for i, m in enumerate(models) if m.startswith("github/")]
        openai_indices = [i for i, m in enumerate(models) if m == "openai"]
        assert github_indices and openai_indices
        assert max(github_indices) < min(openai_indices)
