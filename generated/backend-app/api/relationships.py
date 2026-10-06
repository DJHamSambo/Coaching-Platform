"""Single source of truth for "which coaching relationships can this user see".

A ``Coachee`` row is one coach <-> person relationship. A coachee user can
have several (one per coach); every view that scopes data to a coachee should
go through these helpers rather than querying ``Coachee`` directly, so the
consent rules (``invited``/``declined`` relationships expose nothing) are
enforced the same way everywhere.
"""
from __future__ import annotations

from typing import Optional

from django.contrib.auth.models import User
from django.db.models import QuerySet

from api.models import Coachee
from api.notifications import resolve_recipient

# Relationships whose data the coachee can see: current ones, plus ended ones
# so their history is not lost. Invited/declined relationships expose nothing.
COACHEE_VISIBLE_STATUSES = (Coachee.STATUS_ACTIVE, Coachee.STATUS_ENDED)


def _is_authenticated(user) -> bool:
    return bool(user and getattr(user, "is_authenticated", False))


def _legacy_name_matches(user) -> QuerySet:
    # Legacy coachees created before logins were linked by FK.
    return Coachee.objects.filter(user__isnull=True, name__iexact=user.username)


def is_coachee_user(user) -> bool:
    """True when the user signs in as a coachee (has any relationship row)."""
    if not _is_authenticated(user):
        return False
    return Coachee.objects.filter(user=user).exists() or _legacy_name_matches(user).exists()


def coachee_relationships(user, statuses=COACHEE_VISIBLE_STATUSES) -> QuerySet:
    """The coachee user's relationships, limited to ``statuses``.

    Pass ``statuses=None`` for every relationship regardless of status.
    """
    if not _is_authenticated(user):
        return Coachee.objects.none()
    by_user = Coachee.objects.filter(user=user)
    if not by_user.exists():
        by_user = _legacy_name_matches(user)
    if statuses is not None:
        by_user = by_user.filter(status__in=statuses)
    return by_user


def active_coachee_relationships(user) -> QuerySet:
    return coachee_relationships(user, statuses=(Coachee.STATUS_ACTIVE,))


def coach_relationships(coach) -> QuerySet:
    """Every relationship the coach created, in any status."""
    if not _is_authenticated(coach):
        return Coachee.objects.none()
    return Coachee.objects.filter(added_by=coach)


def coachee_recipient(coachee: Optional[Coachee]) -> Optional[User]:
    """Who to notify about activity in this relationship.

    Nobody while the relationship is awaiting consent: a coach preparing a plan
    for someone who hasn't accepted yet must not reach them.
    """
    if coachee is None:
        return None
    if coachee.user_id:
        return coachee.user if coachee.status == Coachee.STATUS_ACTIVE else None
    return resolve_recipient(coachee.name)
