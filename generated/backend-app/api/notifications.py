"""Helpers for creating activity notifications for coaches and coachees."""
from __future__ import annotations

import re
from typing import Iterable, Optional

from django.contrib.auth.models import User

from api.models import Coachee, Notification

_MENTION_RE = re.compile(r"@([\w.@+-]+)")


def resolve_recipient(name: str) -> Optional[User]:
    """Resolve a mention/assignee name to a User.

    Names may be a login username (coach or coachee account) or a coachee's
    display name. Tries a direct username match first, then falls back to a
    Coachee display-name match with a linked user account.
    """
    if not name:
        return None
    name = name.strip()
    if not name:
        return None

    user = User.objects.filter(username__iexact=name).first()
    if user:
        return user

    coachee = Coachee.objects.filter(name__iexact=name, user__isnull=False).first()
    if coachee and coachee.user:
        return coachee.user
    return None


def notify(
    recipient: Optional[User],
    actor_name: str,
    notification_type: str,
    message: str,
    *,
    target_type: str = "",
    target_id: Optional[int] = None,
    plan_id: Optional[int] = None,
    action_id: Optional[int] = None,
) -> Optional[Notification]:
    """Create a single notification, skipping self-notifications and no-ops."""
    if recipient is None:
        return None
    # Never notify the actor about their own action.
    if actor_name and recipient.username.lower() == actor_name.strip().lower():
        return None
    return Notification.objects.create(
        recipient=recipient,
        actor_name=actor_name or "",
        notification_type=notification_type,
        message=message[:500],
        target_type=target_type,
        target_id=target_id,
        plan_id=plan_id,
        action_id=action_id,
    )


def extract_mentions(text: str) -> list[str]:
    """Pull unique @mention tokens out of free text."""
    if not text:
        return []
    seen: list[str] = []
    for token in _MENTION_RE.findall(text):
        if token not in seen:
            seen.append(token)
    return seen


def notify_mentions(
    actor_name: str,
    text: str,
    *,
    explicit_mentions: str = "",
    area_label: str,
    target_type: str = "",
    target_id: Optional[int] = None,
    plan_id: Optional[int] = None,
    action_id: Optional[int] = None,
    extra_candidates: Optional[Iterable[str]] = None,
) -> None:
    """Notify every mentioned user in a discussion message.

    Mentions are taken from the comma-separated ``explicit_mentions`` field when
    present, otherwise parsed from ``text``. ``extra_candidates`` lets callers
    supply already-known recipient names (e.g. the plan coach) whose mention
    should still resolve even when written as a display name.
    """
    names: list[str] = []
    for chunk in (explicit_mentions or "").split(","):
        chunk = chunk.strip()
        if chunk and chunk not in names:
            names.append(chunk)
    if not names:
        names = extract_mentions(text)

    if not names:
        return

    candidate_lookup = {c.lower(): c for c in (extra_candidates or []) if c}

    for name in names:
        recipient = resolve_recipient(name)
        if recipient is None and name.lower() in candidate_lookup:
            recipient = resolve_recipient(candidate_lookup[name.lower()])
        if recipient is None:
            continue
        preview = text.strip()
        if len(preview) > 140:
            preview = preview[:137] + "..."
        notify(
            recipient,
            actor_name,
            "mention",
            f"{actor_name} mentioned you in {area_label}: \"{preview}\"",
            target_type=target_type,
            target_id=target_id,
            plan_id=plan_id,
            action_id=action_id,
        )
