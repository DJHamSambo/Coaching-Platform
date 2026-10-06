"""Coaching relationship consent and coachee-controlled data sharing.

Coachee side: list relationships, accept/decline invitations, end a
relationship, and choose which plans, insights and questionnaires from other
relationships a coach may see. Coach side: a read-only view of what a coachee
has shared with them. Nothing is ever shared by default.
"""
from __future__ import annotations

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from api.models import Coachee, CoachingPlan, DataShare, FoundationalQuestionnaire, Insight
from api.notifications import notify
from api.relationships import coachee_relationships

_PREVIEW_CHARS = 140


def _preview(text: str) -> str:
    text = (text or "").strip()
    return text if len(text) <= _PREVIEW_CHARS else text[: _PREVIEW_CHARS - 3] + "..."


def _coach_name(coachee: Coachee) -> str:
    coach = coachee.added_by
    return (coach.get_full_name() or coach.username).strip()


def _serialize_relationship(rel: Coachee) -> dict:
    return {
        "id": rel.id,
        "coach_id": rel.added_by_id,
        "coach_username": rel.added_by.username,
        "coach_name": _coach_name(rel),
        "status": rel.status,
        "created_at": rel.created_at,
        "responded_at": rel.responded_at,
        "active_share_count": rel.received_shares.filter(revoked_at__isnull=True).count(),
    }


def _own_relationship(user, pk) -> Coachee:
    """A relationship belonging to the signed-in coachee (any status)."""
    rel = coachee_relationships(user, statuses=None).select_related("added_by").filter(pk=pk).first()
    if rel is None:
        raise PermissionDenied("This coaching relationship isn't yours.")
    return rel


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_relationships(request: Request) -> Response:
    """The signed-in coachee's coaching relationships, newest first.

    Declined invitations are left out; the coach who sent them still sees the
    outcome on their side.
    """
    rels = (
        coachee_relationships(request.user, statuses=None)
        .exclude(status=Coachee.STATUS_DECLINED)
        .select_related("added_by")
        .order_by("-created_at")
    )
    return Response([_serialize_relationship(rel) for rel in rels])


def _respond(request: Request, pk: int, *, from_status: str, to_status: str, notification_type: str, verb: str) -> Response:
    rel = _own_relationship(request.user, pk)
    if rel.status != from_status:
        raise ValidationError({"status": [f"This relationship is {rel.get_status_display().lower()}, so it can't be {verb}."]})
    rel.status = to_status
    rel.responded_at = timezone.now()
    rel.save(update_fields=["status", "responded_at"])
    notify(
        rel.added_by,
        request.user.username,
        notification_type,
        f"{rel.name} {verb} your coaching invitation." if from_status == Coachee.STATUS_INVITED
        else f"{rel.name} ended your coaching relationship.",
        target_type="coachee",
        target_id=rel.id,
    )
    return Response(_serialize_relationship(rel))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def accept_relationship(request: Request, pk: int) -> Response:
    return _respond(
        request, pk,
        from_status=Coachee.STATUS_INVITED, to_status=Coachee.STATUS_ACTIVE,
        notification_type="invitation_accepted", verb="accepted",
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def decline_relationship(request: Request, pk: int) -> Response:
    return _respond(
        request, pk,
        from_status=Coachee.STATUS_INVITED, to_status=Coachee.STATUS_DECLINED,
        notification_type="invitation_declined", verb="declined",
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def end_relationship(request: Request, pk: int) -> Response:
    """End an active relationship. Either the coachee or the coach may do this.

    History is kept: the coachee still sees what was created, and shares made
    to this coach stop being served because the relationship is no longer active.
    """
    rel = get_object_or_404(Coachee.objects.select_related("added_by", "user"), pk=pk)
    is_coach = rel.added_by_id == request.user.id
    if not is_coach:
        return _respond(
            request, pk,
            from_status=Coachee.STATUS_ACTIVE, to_status=Coachee.STATUS_ENDED,
            notification_type="relationship_ended", verb="ended",
        )
    if rel.status != Coachee.STATUS_ACTIVE:
        raise ValidationError({"status": ["Only an active relationship can be ended."]})
    rel.status = Coachee.STATUS_ENDED
    rel.responded_at = timezone.now()
    rel.save(update_fields=["status", "responded_at"])
    if rel.user_id:
        notify(
            rel.user,
            request.user.username,
            "relationship_ended",
            f"{_coach_name(rel)} ended your coaching relationship.",
            target_type="relationship",
            target_id=rel.id,
        )
    return Response(_serialize_relationship(rel))


# ---------------------------------------------------------------------------
# Coachee-controlled sharing
# ---------------------------------------------------------------------------

def _shareable_querysets(user, target: Coachee) -> dict:
    """Items the coachee may share with ``target``: anything from their other
    relationships (current or past) plus their own private reflections."""
    others = coachee_relationships(user).exclude(pk=target.pk)
    return {
        "plan": CoachingPlan.objects.filter(coachee__in=others).select_related("coachee__added_by"),
        "insight": Insight.objects.filter(
            Q(coachee__in=others) | Q(owner=user, coachee__isnull=True)
        ).select_related("coachee__added_by"),
        "questionnaire": FoundationalQuestionnaire.objects.filter(owner=user)
        .exclude(coachee=target)
        .select_related("coachee__added_by"),
    }


def _source_label(item_coachee) -> str:
    return f"With {_coach_name(item_coachee)}" if item_coachee else "Private"


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def shareable_items(request: Request, pk: int) -> Response:
    """Everything the coachee could share with this coach, flagged with the
    active share (if any) so the UI can show a toggle per item."""
    target = _own_relationship(request.user, pk)
    active_shares = {
        (share.item_type, share.item_id): share.id
        for share in target.received_shares.filter(revoked_at__isnull=True)
    }
    sets = _shareable_querysets(request.user, target)
    return Response({
        "plans": [
            {
                "id": plan.id,
                "label": plan.title,
                "source": _source_label(plan.coachee),
                "share_id": active_shares.get(("plan", plan.id)),
            }
            for plan in sets["plan"].order_by("-created_at")
        ],
        "insights": [
            {
                "id": insight.id,
                "label": _preview(insight.title),
                "source": _source_label(insight.coachee),
                "share_id": active_shares.get(("insight", insight.id)),
            }
            for insight in sets["insight"].order_by("-created_at")
        ],
        "questionnaires": [
            {
                "id": q.id,
                "label": f"{q.name or 'Foundational questionnaire'} ({q.submitted_at:%d %b %Y})",
                "source": _source_label(q.coachee),
                "share_id": active_shares.get(("questionnaire", q.id)),
            }
            for q in sets["questionnaire"].order_by("-submitted_at")
        ],
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_share(request: Request, pk: int) -> Response:
    target = _own_relationship(request.user, pk)
    if target.status != Coachee.STATUS_ACTIVE:
        raise ValidationError({"detail": ["You can only share with a coach you're currently working with."]})

    item_type = str(request.data.get("item_type", ""))
    if item_type not in DataShare.ITEM_TYPES:
        raise ValidationError({"item_type": [f"Must be one of: {', '.join(DataShare.ITEM_TYPES)}."]})
    try:
        item_id = int(request.data.get("item_id"))
    except (TypeError, ValueError):
        raise ValidationError({"item_id": ["A valid item id is required."]})

    item = _shareable_querysets(request.user, target)[item_type].filter(pk=item_id).first()
    if item is None:
        raise PermissionDenied("You can't share that item with this coach.")

    try:
        with transaction.atomic():
            share = DataShare.objects.create(granted_to=target, granted_by=request.user, **{item_type: item})
    except IntegrityError:
        # Already shared; sharing is idempotent.
        share = target.received_shares.get(revoked_at__isnull=True, **{item_type: item})
        return Response({"id": share.id, "item_type": item_type, "item_id": item_id}, status=status.HTTP_200_OK)

    notify(
        target.added_by,
        request.user.username,
        "data_shared",
        f"{target.name} shared a {item_type} from a previous coaching engagement with you.",
        target_type="coachee",
        target_id=target.id,
    )
    return Response({"id": share.id, "item_type": item_type, "item_id": item_id}, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def revoke_share(request: Request, pk: int, share_id: int) -> Response:
    target = _own_relationship(request.user, pk)
    share = target.received_shares.filter(pk=share_id, revoked_at__isnull=True).first()
    if share is None:
        raise PermissionDenied("That share doesn't exist or was already revoked.")
    share.revoked_at = timezone.now()
    share.save(update_fields=["revoked_at"])
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Coach side: read-only view of what a coachee shared
# ---------------------------------------------------------------------------

def _insight_author_label(insight: Insight, coachee_user_id) -> str:
    # Never name the coach from another engagement; the coachee shared the
    # content, not an introduction.
    return "Coachee" if insight.owner_id == coachee_user_id else "Previous coach"


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def coachee_shared_data(request: Request, pk: int) -> Response:
    """Items the coachee has shared into this coach's relationship. Read-only."""
    rel = get_object_or_404(Coachee, pk=pk)
    if rel.added_by_id != request.user.id and not request.user.is_staff:
        raise PermissionDenied("You do not have access to this coachee.")
    if rel.status != Coachee.STATUS_ACTIVE:
        return Response({"plans": [], "insights": [], "questionnaires": []})

    shares = rel.received_shares.filter(revoked_at__isnull=True).select_related(
        "plan", "insight", "questionnaire"
    ).prefetch_related("plan__actions")
    plans, insights, questionnaires = [], [], []
    for share in shares:
        if share.plan_id:
            plan = share.plan
            plans.append({
                "share_id": share.id,
                "shared_at": share.created_at,
                "id": plan.id,
                "title": plan.title,
                "description": plan.description,
                "goal": plan.goal,
                "status": plan.status,
                "target_date": plan.target_date,
                "actions": [
                    {"title": a.title, "status": a.status, "due_date": a.due_date}
                    for a in plan.actions.all()
                ],
            })
        elif share.insight_id:
            insight = share.insight
            insights.append({
                "share_id": share.id,
                "shared_at": share.created_at,
                "id": insight.id,
                "note": insight.title,
                "author": _insight_author_label(insight, rel.user_id),
                "created_at": insight.created_at,
            })
        else:
            q = share.questionnaire
            questionnaires.append({
                "share_id": share.id,
                "shared_at": share.created_at,
                "id": q.id,
                "name": q.name,
                "answers": q.answers,
                "submitted_at": q.submitted_at,
            })
    return Response({"plans": plans, "insights": insights, "questionnaires": questionnaires})
