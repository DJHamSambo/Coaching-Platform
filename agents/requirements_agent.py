from __future__ import annotations

import argparse
import ipaddress
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class SourceDocument:
    kind: str
    location: str
    content: str


@dataclass(frozen=True)
class RequirementsResult:
    title: str
    summary: list[str]
    functional_requirements: list[str]
    non_functional_requirements: list[str]
    constraints: list[str]
    open_questions: list[str]
    sources: list[str]

    def to_markdown(self) -> str:
        sections = [
            ("Summary", self.summary),
            ("Functional requirements", self.functional_requirements),
            ("Non-functional requirements", self.non_functional_requirements),
            ("Constraints and assumptions", self.constraints),
            ("Open questions", self.open_questions),
            ("Sources", self.sources),
        ]
        lines = [f"# {self.title}", ""]
        for heading, items in sections:
            lines.extend([f"## {heading}"])
            if items:
                lines.extend(f"- {item}" for item in items)
            else:
                lines.append("- None identified")
            lines.append("")
        return "\n".join(lines).strip() + "\n"


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._ignored_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        cleaned = re.sub(r"\s+", " ", data).strip()
        if cleaned:
            self._parts.append(cleaned)

    def text(self) -> str:
        return "\n".join(self._parts)


class RequirementsAgent:
    FUNCTIONAL_HINTS = (
        "must",
        "should",
        "shall",
        "needs to",
        "need to",
        "allow",
        "support",
        "enable",
        "provide",
        "create",
        "build",
        "include",
        "capture",
        "generate",
        "process",
        "manage",
        "accept",
        "take",
    )
    NON_FUNCTIONAL_HINTS = (
        "security",
        "secure",
        "reliable",
        "reliability",
        "performance",
        "maintainable",
        "scalable",
        "accessible",
        "documentation",
        "document",
        "tested",
        "testing",
        "observability",
        "monitoring",
        "audit",
    )
    CONSTRAINT_HINTS = (
        "use ",
        "within ",
        "limit",
        "cannot",
        "can't",
        "must not",
        "should not",
        "do not",
        "don't",
        "avoid",
        "requires",
        "depends on",
        "branch",
        "python",
        "markdown",
    )
    QUESTION_HINTS = ("?", "tbd", "unclear", "unknown", "to be decided")

    def distill(
        self,
        texts: Iterable[str] | None = None,
        file_paths: Iterable[str | Path] | None = None,
        urls: Iterable[str] | None = None,
        title: str = "Development Requirements",
    ) -> RequirementsResult:
        sources = self._collect_sources(texts or [], file_paths or [], urls or [])
        candidates = self._extract_candidates(source.content for source in sources)

        summary = self._unique(self._select_summary(candidates))[:3]
        functional = self._unique(self._classify(candidates, self.FUNCTIONAL_HINTS))[:12]
        non_functional = self._unique(self._classify(candidates, self.NON_FUNCTIONAL_HINTS))[:8]
        constraints = self._unique(self._classify(candidates, self.CONSTRAINT_HINTS))[:8]
        open_questions = self._unique(
            sentence for sentence in candidates if self._contains_hint(sentence, self.QUESTION_HINTS)
        )[:8]

        if not functional:
            functional = summary[:]

        return RequirementsResult(
            title=title,
            summary=summary or ["Summarise the provided inputs before implementation begins."],
            functional_requirements=functional,
            non_functional_requirements=non_functional,
            constraints=constraints,
            open_questions=open_questions,
            sources=[f"{source.kind}: {source.location}" for source in sources],
        )

    def _collect_sources(
        self,
        texts: Iterable[str],
        file_paths: Iterable[str | Path],
        urls: Iterable[str],
    ) -> list[SourceDocument]:
        sources: list[SourceDocument] = []
        for index, text in enumerate(texts, start=1):
            cleaned = text.strip()
            if cleaned:
                sources.append(SourceDocument("text", f"text-{index}", cleaned))
        for file_path in file_paths:
            path = Path(file_path)
            sources.append(SourceDocument("file", str(path), path.read_text(encoding="utf-8")))
        for url in urls:
            sources.append(SourceDocument("url", url, self.fetch_url_text(url)))
        if not sources:
            raise ValueError("At least one text input, file path, or URL is required.")
        return sources

    def fetch_url_text(self, url: str, timeout: int = 10) -> str:
        self._validate_url(url)
        request = Request(url, headers={"User-Agent": "RequirementsAgent/1.0"})
        with urlopen(request, timeout=timeout) as response:  # nosec B310
            html = response.read().decode("utf-8", errors="ignore")
        parser = _HTMLTextExtractor()
        parser.feed(html)
        return parser.text()

    def _extract_candidates(self, contents: Iterable[str]) -> list[str]:
        candidates: list[str] = []
        for content in contents:
            normalised = re.sub(r"\r\n?", "\n", content)
            for block in re.split(r"\n+", normalised):
                cleaned_block = re.sub(r"^[\-\*\d\.\)\s]+", "", block).strip()
                if not cleaned_block:
                    continue
                parts = re.split(r"(?<=[.!?])\s+", cleaned_block)
                for part in parts:
                    sentence = re.sub(r"\s+", " ", part).strip(" -")
                    if len(sentence) >= 12:
                        candidates.append(sentence)
        return candidates

    def _select_summary(self, sentences: Iterable[str]) -> list[str]:
        return [sentence for sentence in sentences if not self._contains_hint(sentence, self.QUESTION_HINTS)][:3]

    def _classify(self, sentences: Iterable[str], hints: Iterable[str]) -> list[str]:
        return [sentence for sentence in sentences if self._contains_hint(sentence, hints)]

    @staticmethod
    def _contains_hint(sentence: str, hints: Iterable[str]) -> bool:
        lowered = sentence.lower()
        return any(hint in lowered for hint in hints)

    @staticmethod
    def _unique(items: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        unique_items: list[str] = []
        for item in items:
            normalised = item.strip()
            key = normalised.lower()
            if normalised and key not in seen:
                seen.add(key)
                unique_items.append(normalised)
        return unique_items

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Only http and https URLs are supported.")
        if not parsed.hostname:
            raise ValueError("URL must include a hostname.")
        if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Localhost URLs are not allowed.")

        try:
            addresses = {
                sockaddr[0]
                for _, _, _, _, sockaddr in socket.getaddrinfo(parsed.hostname, None, type=socket.SOCK_STREAM)
            }
        except socket.gaierror:
            return

        for address in addresses:
            ip = ipaddress.ip_address(address)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                raise ValueError("Only publicly routable website URLs are allowed.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Distil raw material into implementation-ready requirements.")
    parser.add_argument("--text", action="append", default=[], help="Inline text to analyse.")
    parser.add_argument("--file", action="append", default=[], help="Path to a text file to analyse.")
    parser.add_argument("--url", action="append", default=[], help="URL to fetch and analyse.")
    parser.add_argument("--title", default="Development Requirements", help="Markdown document title.")
    parser.add_argument("--output", help="Optional output markdown file path.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    result = RequirementsAgent().distill(
        texts=args.text,
        file_paths=args.file,
        urls=args.url,
        title=args.title,
    )
    markdown = result.to_markdown()
    if args.output:
        Path(args.output).write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
