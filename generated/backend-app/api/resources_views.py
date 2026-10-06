from django.contrib.auth.models import User
from django.db.models import Q
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied

from api.models import Coachee, CoachingPlan, Resource
from api.notifications import notify
from api.plans_views import _resolve_owner
from api.relationships import (
    active_coachee_relationships,
    coach_relationships,
    coachee_relationships as _linked_coachee_profiles,
    is_coachee_user as _is_coachee_user,
)
from api.resources_serializers import ResourcesSerializer


def _accessible_plans(request):
    """Coaching plans the requesting user participates in (as coach or coachee)."""
    if _is_coachee_user(request.user):
        return CoachingPlan.objects.filter(coachee__in=_linked_coachee_profiles(request.user))
    return CoachingPlan.objects.filter(coach=_resolve_owner(request))


def _validate_plan_link(request, plan):
    """Reject linking a resource to a plan the user does not participate in."""
    if plan is None:
        return
    if not _accessible_plans(request).filter(pk=plan.pk).exists():
        raise PermissionDenied("You do not have access to the selected coaching plan.")


def _validate_shared_with(request, users):
    """Only share with people the requester actually works with.

    Coachees may share with their current coaches; coaches may share with
    other coaches and with coachees who have accepted a relationship with them.
    Without this anyone could push a resource to any account by username.
    """
    user = request.user
    if not users or user.is_staff:
        return
    if _is_coachee_user(user):
        allowed_ids = set(active_coachee_relationships(user).values_list("added_by_id", flat=True))
    else:
        coach_ids = set(
            User.objects.exclude(coachee_profiles__isnull=False).values_list("id", flat=True)
        )
        coachee_ids = set(
            coach_relationships(user)
            .filter(status=Coachee.STATUS_ACTIVE, user__isnull=False)
            .values_list("user_id", flat=True)
        )
        allowed_ids = coach_ids | coachee_ids
    for target in users:
        if target.id != user.id and target.id not in allowed_ids:
            raise PermissionDenied(f"You can't share resources with {target.username}.")


class ResourcesListView(generics.ListCreateAPIView):
    serializer_class = ResourcesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        accessible_plan_ids = _accessible_plans(self.request).values_list("id", flat=True)
        queryset = Resource.objects.filter(
            Q(owner=user) | Q(plan_id__in=list(accessible_plan_ids)) | Q(shared_with=user)
        ).distinct()
        plan_id = self.request.query_params.get("plan")
        if plan_id:
            queryset = queryset.filter(plan_id=plan_id)
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        _validate_plan_link(self.request, serializer.validated_data.get("plan"))
        _validate_shared_with(self.request, serializer.validated_data.get("shared_with"))
        resource = serializer.save(owner=self.request.user)

        # Notify each user the resource was explicitly shared with.
        actor_name = getattr(self.request.user, "username", "") or ""
        for recipient in resource.shared_with.all():
            notify(
                recipient,
                actor_name,
                "resource_added",
                f'{actor_name} shared a resource with you: {resource.title}',
                target_type="resource",
                target_id=resource.id,
            )


class ResourcesDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ResourcesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        accessible_plan_ids = _accessible_plans(self.request).values_list("id", flat=True)
        return Resource.objects.filter(
            Q(owner=user) | Q(plan_id__in=list(accessible_plan_ids)) | Q(shared_with=user)
        ).distinct()

    def perform_update(self, serializer):
        _validate_plan_link(self.request, serializer.validated_data.get("plan", serializer.instance.plan))
        _validate_shared_with(self.request, serializer.validated_data.get("shared_with"))
        serializer.save()

    def perform_destroy(self, instance):
        if instance.owner_id != self.request.user.id:
            raise PermissionDenied("You can only delete resources you uploaded.")
        instance.delete()
