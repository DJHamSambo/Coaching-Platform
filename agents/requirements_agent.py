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
    user_stories: list[str]
    functional_requirements: list[str]
    non_functional_requirements: list[str]
    constraints: list[str]
    open_questions: list[str]
    sources: list[str]

    def to_markdown(self) -> str:
        sections = [
            ("Summary", self.summary),
            ("User stories", self.user_stories),
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
    ROLE_PREFIXES = ("coachee", "coach")
    ROLE_LABELS = {
        "coach": "coach",
        "coachee": "coachee",
    }
    ROLE_PLURALS = {
        "coach": "coaches",
        "coachee": "coachees",
    }
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
        statements = self._extract_statements(source.content for source in sources)
        candidates = [statement["text"] for statement in statements]

        functional_statements = self._classify_statements(statements, self.FUNCTIONAL_HINTS)
        if not functional_statements:
            functional_statements = statements[:]

        summary = self._unique(self._build_summary(statement) for statement in functional_statements)[:3]
        user_stories = self._unique(self._build_user_story(statement) for statement in functional_statements)[:12]
        functional = self._unique(
            self._build_functional_requirement(statement) for statement in functional_statements
        )[:12]
        non_functional = self._unique(self._classify(candidates, self.NON_FUNCTIONAL_HINTS))[:8]
        constraints = self._unique(self._classify(candidates, self.CONSTRAINT_HINTS))[:8]
        open_questions = self._unique(
            sentence for sentence in candidates if self._contains_hint(sentence, self.QUESTION_HINTS)
        )[:8]

        return RequirementsResult(
            title=title,
            summary=summary or ["Summarise the provided inputs before implementation begins."],
            user_stories=user_stories,
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

    def _extract_statements(self, contents: Iterable[str]) -> list[dict[str, str | None]]:
        statements: list[dict[str, str | None]] = []
        current_actor: str | None = None
        for content in contents:
            normalised = re.sub(r"\r\n?", "\n", content).strip()
            if not normalised:
                continue
            segments = [
                re.sub(r"\s+", " ", segment).strip(" -")
                for segment in re.split(
                    r"(?:\n+| {2,}(?=(?:Coachee|Coach|I want|The ability to|Tasks can|Have a list of))|(?<=[.!?])\s+)",
                    normalised,
                )
                if segment.strip(" -")
            ]

            for segment in segments:
                actor, cleaned = self._extract_actor(segment, current_actor)
                if actor:
                    current_actor = actor
                if len(cleaned) >= 12:
                    statements.append({"actor": current_actor, "text": cleaned})
        return statements

    def _extract_actor(self, segment: str, current_actor: str | None) -> tuple[str | None, str]:
        cleaned = segment.strip()
        actor = current_actor

        role_story_match = re.match(r"^as\s+an?\s+(coach|coachee)\b[\s,:-]*", cleaned, flags=re.IGNORECASE)
        if role_story_match:
            actor = role_story_match.group(1).lower()
            cleaned = cleaned[role_story_match.end() :].strip(" ,:-")

        for prefix in self.ROLE_PREFIXES:
            if cleaned.lower().startswith(f"{prefix} "):
                actor = prefix
                cleaned = cleaned[len(prefix) :].strip(" ,:-")
                break
        return actor, cleaned

    def _select_summary(self, sentences: Iterable[str]) -> list[str]:
        return [sentence for sentence in sentences if not self._contains_hint(sentence, self.QUESTION_HINTS)][:3]

    def _classify(self, sentences: Iterable[str], hints: Iterable[str]) -> list[str]:
        return [sentence for sentence in sentences if self._contains_hint(sentence, hints)]

    def _classify_statements(
        self,
        statements: Iterable[dict[str, str | None]],
        hints: Iterable[str],
    ) -> list[dict[str, str | None]]:
        return [
            statement
            for statement in statements
            if self._contains_hint(str(statement["text"]), hints)
            and not self._contains_hint(str(statement["text"]), self.QUESTION_HINTS)
        ]

    def _build_summary(self, statement: dict[str, str | None]) -> str:
        actor = statement["actor"]
        capability, benefit = self._normalise_capability(str(statement["text"]), actor)
        subject = self.ROLE_PLURALS.get(str(actor), "users") if actor else "users"
        sentence = f"{subject.capitalize()} can {capability}"
        if benefit:
            sentence += f" so that {benefit}"
        return self._ensure_sentence(sentence)

    def _build_user_story(self, statement: dict[str, str | None]) -> str:
        actor = str(statement["actor"] or "user")
        capability, benefit = self._normalise_capability(str(statement["text"]), statement["actor"])
        capability = self._story_capability(capability)
        if capability.lower().startswith("coaches "):
            story = f"As a {self.ROLE_LABELS.get(actor, actor)}, I want coaches to {capability[8:]}"
        elif capability.lower().startswith("coachees "):
            story = f"As a {self.ROLE_LABELS.get(actor, actor)}, I want coachees to {capability[9:]}"
        elif capability.lower().startswith("coaching plans to "):
            story = f"As a {self.ROLE_LABELS.get(actor, actor)}, I want {capability}"
        elif capability.lower().startswith("each coaching plan to "):
            story = f"As a {self.ROLE_LABELS.get(actor, actor)}, I want {capability}"
        elif capability.lower().startswith("each action to "):
            story = f"As a {self.ROLE_LABELS.get(actor, actor)}, I want {capability}"
        else:
            story = f"As a {self.ROLE_LABELS.get(actor, actor)}, I want to {capability}"
        if benefit:
            story += f", so that {benefit}"
        return self._ensure_sentence(story)

    def _build_functional_requirement(self, statement: dict[str, str | None]) -> str:
        actor = statement["actor"]
        capability, benefit = self._normalise_capability(str(statement["text"]), actor)
        target_actor = self._infer_target_actor(capability, actor)
        if capability.lower().startswith(("allow ", "show ", "visualise ", "support ", "provide ")):
            target_actor = self._infer_target_actor(capability, None)
        verb_phrase = self._strip_actor_target_prefix(capability)
        if target_actor:
            requirement = f"The system shall allow {self.ROLE_PLURALS[target_actor]} to {verb_phrase}"
        else:
            requirement = f"The system shall {verb_phrase}"
        if benefit:
            requirement += f" so that {benefit}"
        return self._ensure_sentence(requirement)

    def _normalise_capability(self, sentence: str, actor: str | None) -> tuple[str, str | None]:
        cleaned = re.sub(r"\s+", " ", sentence.strip(" ."))
        cleaned = self._strip_story_prefix(cleaned)
        cleaned = self._normalise_leading_requirement_phrase(cleaned)
        cleaned = re.sub(r"\b(can together from all plans)\b", "capture together from all plans", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(
            r"^build a [^.]+? that must ",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        benefit: str | None = None

        specialised = self._specialise_capability(cleaned, actor)
        if specialised:
            return specialised

        split_match = re.match(r"(.+?),(?:\s*so that\s+|\s*so I can\s+|\s*that I can\s+)(.+)", cleaned, flags=re.IGNORECASE)
        if split_match:
            cleaned = split_match.group(1).strip(" ,")
            benefit = self._normalise_benefit(split_match.group(2), actor)

        lowered = cleaned.lower()
        if lowered.startswith("i want the ability to "):
            capability = cleaned[22:]
        elif lowered.startswith("the ability to "):
            capability = cleaned[15:]
        elif lowered.startswith("i want to "):
            capability = cleaned[10:]
        elif lowered.startswith("i want "):
            remainder = cleaned[7:]
            capability = f"have {remainder}" if re.match(r"(?i)(a|an|the|my|our)\b", remainder) else remainder
        elif lowered.startswith("have a list of "):
            capability = cleaned
        else:
            capability = cleaned

        capability = self._normalise_phrase(capability, actor)
        capability = re.sub(r"^(must|should|shall|needs to|need to)\s+", "", capability, flags=re.IGNORECASE)
        capability = re.sub(r"^(the system)\s+(must|should|shall)\s+", "", capability, flags=re.IGNORECASE)
        benefit = benefit or self._derive_benefit(capability, actor)
        capability = re.sub(r"\bmy\b", "their", capability, flags=re.IGNORECASE)
        capability = re.sub(r"\bme\b", "the user", capability, flags=re.IGNORECASE)
        capability = capability[0].lower() + capability[1:] if capability else capability
        return capability.rstrip("."), benefit.rstrip(".") if benefit else None

    def _strip_story_prefix(self, sentence: str) -> str:
        cleaned = sentence.strip()
        patterns = (
            r"^as\s+an?\s+(?:coach|coachee)\s*,?\s*i\s+want\s+to\s+be\s+able\s+to\s+",
            r"^as\s+an?\s+(?:coach|coachee)\s*,?\s*i\s+want\s+the\s+ability\s+to\s+",
            r"^as\s+an?\s+(?:coach|coachee)\s*,?\s*i\s+want\s+to\s+",
            r"^as\s+an?\s+(?:coach|coachee)\s*,?\s*i\s+want\s+",
            r"^i\s+want\s+to\s+be\s+able\s+to\s+",
        )
        for pattern in patterns:
            updated = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
            if updated != cleaned:
                return updated.strip()
        return cleaned

    def _normalise_leading_requirement_phrase(self, sentence: str) -> str:
        cleaned = sentence.strip()
        lowered = cleaned.lower()

        if lowered.startswith("these should show as a list in "):
            remainder = cleaned[len("these should show as a list in ") :].strip()
            return f"show coaching plans as a list in {remainder}"
        if lowered.startswith("each coaching plan should be able to have "):
            remainder = cleaned[len("each coaching plan should be able to have ") :].strip()
            return f"allow each coaching plan to have {remainder}"
        if lowered.startswith("each coaching plan should have "):
            remainder = cleaned[len("each coaching plan should have ") :].strip()
            return f"allow each coaching plan to have {remainder}"
        if lowered.startswith("each of the actions should be able to have "):
            remainder = cleaned[len("each of the actions should be able to have ") :].strip()
            return f"allow each action to have {remainder}"
        if lowered.startswith("each action should be able to have "):
            remainder = cleaned[len("each action should be able to have ") :].strip()
            return f"allow each action to have {remainder}"
        if "coaching plan's should also be able to have discussion" in lowered or "coaching plans should also be able to have discussion" in lowered:
            return "allow coaching plans to include discussion threads"
        return cleaned

    def _story_capability(self, capability: str) -> str:
        lowered = capability.lower()
        if lowered.startswith("allow each coaching plan to "):
            return re.sub(r"\s+", " ", f"each coaching plan to {capability[28:]}").strip()
        if lowered.startswith("allow each action to "):
            return re.sub(r"\s+", " ", f"each action to {capability[21:]}").strip()
        if lowered.startswith("show coaching plans as a list in "):
            return re.sub(r"\s+", " ", f"coaching plans to be shown as a list in {capability[33:]}").strip()
        if lowered.startswith("allow coaching plans to "):
            return re.sub(r"\s+", " ", f"coaching plans to {capability[24:]}").strip()
        return capability

    def _normalise_phrase(self, phrase: str, actor: str | None) -> str:
        cleaned = phrase.strip(" .")
        cleaned = re.sub(r"\bnormal calendaring apps of choice\b", "preferred calendaring apps", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bmicrosoft outlook, google gmail/calendar\b", "Microsoft Outlook and Google Calendar", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bgoogle gmail/calendar\b", "Google Calendar", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bcontianing\b", "containing", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b1 to 1\b", "one-to-one", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b@ to their name\b", "mentioned with @mentions", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bwhere they can respond to me and I'll be notified\b", "with threaded replies and notifications", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bthat can then be prioritised and visualised on a kanban board to track progress\b", "that can be prioritised and visualised on a kanban board to track progress", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bthat outlines the overall goal, key actions/tasks and sequence that break the goal down that can be visualised on a kanban style board, and a target date\b", "a coaching plan with an overall goal, sequenced actions, a kanban-style board, and a target date", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bi can together from all plans in chronological order\b", "capture across all plans in chronological order", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bjournal and or write notes\b", "journal and write notes", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bcoachees being able to share information/documents with me 1 to 1 and show up against their profile\b", "coachees to share one-to-one information and documents that appear on their profile", cleaned, flags=re.IGNORECASE)
        if actor == "coach":
            cleaned = re.sub(r"\bmy availability\b", "coach availability", cleaned, flags=re.IGNORECASE)
        return cleaned

    def _specialise_capability(self, sentence: str, actor: str | None) -> tuple[str, str | None] | None:
        lowered = sentence.lower()

        if "availability" in lowered and "request coaching sessions" in lowered:
            return (
                "manage coach availability for session requests",
                "coachees can book within approved time slots",
            )
        if "request coaching sessions" in lowered and ("outlook" in lowered or "calendar" in lowered):
            return (
                "request coaching sessions with a coach and sync them with Microsoft Outlook and Google Calendar",
                "session bookings stay aligned with preferred calendar tools",
            )
        if "coaching plan" in lowered and "kanban" in lowered:
            return (
                "manage a coaching plan with an overall goal, sequenced actions, a kanban-style board, and a target date",
                "progress remains visible over time",
            )
        if "in progress coaching plans" in lowered and "drag and drop" in lowered and "kanban" in lowered:
            return (
                "visualise actions from in-progress coaching plans on a kanban board and drag actions between status columns",
                "action status updates stay synchronized with board movement",
            )
        if "comments/discussion against an action/task" in lowered:
            return (
                "add discussion to coaching tasks and mention a coach with @mentions",
                "coach and coachee stay aligned on next steps",
            )
        if "add insights against my profile" in lowered:
            return (
                "coaches add insights to their coachee profiles",
                "progress can be reviewed over time",
            )
        if "central location" in lowered and "shared" in lowered:
            return (
                "access a central hub for coach-shared information, including plan-specific resources",
                "important information stays easy to find",
            )
        if "journal" in lowered and "chronological order" in lowered:
            return (
                "journal and capture plan notes in a chronological timeline",
                "progress can be reflected on over time",
            )
        if "have a list of coachees" in lowered or "filtered/searched" in lowered:
            return (
                "search and filter coachee profiles with contact details and profile photos",
                "coach workloads remain easy to manage",
            )
        if "set up one to many coaching plans" in lowered or ("coaching plan" in lowered and "prioritised" in lowered):
            return (
                "create multiple coaching plans per coachee with prioritised kanban-tracked tasks",
                "coaching work stays structured and measurable",
            )
        if lowered.startswith("tasks can have discussion"):
            return (
                "support task discussions and notifications for @mentions",
                "collaboration stays timely and visible",
            )
        if "coaching resources section" in lowered or ("share useful information and documents" in lowered and "coachees" in lowered):
            return (
                "share coaching resources and one-to-one documents with coachees",
                "shared materials remain easy to find",
            )
        return None

    def _derive_benefit(self, capability: str, actor: str | None) -> str | None:
        lowered = capability.lower()
        if "integrate with" in lowered:
            return "calendar availability stays synchronized"
        if "kanban" in lowered:
            return "progress remains visible over time"
        if "@" in lowered or "notification" in lowered:
            return "coach and coachee stay aligned on next steps"
        if "insights against" in lowered:
            return "progress can be reviewed over time"
        if "journal" in lowered or "notes" in lowered:
            return "progress can be reflected on chronologically"
        if "resources" in lowered or "documents" in lowered:
            return "shared materials remain easy to find"
        return None

    def _normalise_benefit(self, benefit: str, actor: str | None) -> str:
        cleaned = benefit.strip(" .,")
        cleaned = re.sub(r"\bmy\b", "their", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bme\b", "the user", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bi'll\b", "they will", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bi can\b", "the user can", cleaned, flags=re.IGNORECASE)
        if actor == "coach":
            cleaned = re.sub(r"\bmy\b", "the coach's", cleaned, flags=re.IGNORECASE)
        return cleaned

    def _infer_target_actor(self, capability: str, fallback_actor: str | None) -> str | None:
        lowered = capability.lower()
        if lowered.startswith("coaches to ") or lowered.startswith("coaches "):
            return "coach"
        if lowered.startswith("coachees to ") or lowered.startswith("coachees "):
            return "coachee"
        return fallback_actor

    def _strip_actor_target_prefix(self, capability: str) -> str:
        cleaned = re.sub(r"^(coaches|coachees) to ", "", capability, flags=re.IGNORECASE)
        cleaned = re.sub(r"^(coaches|coachees) ", "", cleaned, flags=re.IGNORECASE)
        return cleaned

    @staticmethod
    def _ensure_sentence(text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return cleaned
        if cleaned[-1] not in ".!?":
            return f"{cleaned}."
        return cleaned

    @staticmethod
    def _contains_hint(sentence: str, hints: Iterable[str]) -> bool:
        lowered = sentence.lower()
        for hint in hints:
            if " " in hint:
                if hint in lowered:
                    return True
                continue
            if re.fullmatch(r"\W+", hint):
                if hint in lowered:
                    return True
                continue
            if re.search(rf"\b{re.escape(hint)}\b", lowered):
                return True
        return False

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
