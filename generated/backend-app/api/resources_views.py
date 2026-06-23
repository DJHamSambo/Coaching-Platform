from django.db.models import Q
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied

from api.models import CoachingPlan, Resource
from api.plans_views import _is_coachee_user, _linked_coachee_profiles, _resolve_owner
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


class ResourcesListView(generics.ListCreateAPIView):
    serializer_class = ResourcesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        accessible_plan_ids = _accessible_plans(self.request).values_list("id", flat=True)
        queryset = Resource.objects.filter(
            Q(owner=user) | Q(plan_id__in=list(accessible_plan_ids))
        ).distinct()
        plan_id = self.request.query_params.get("plan")
        if plan_id:
            queryset = queryset.filter(plan_id=plan_id)
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        _validate_plan_link(self.request, serializer.validated_data.get("plan"))
        serializer.save(owner=self.request.user)


class ResourcesDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ResourcesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        accessible_plan_ids = _accessible_plans(self.request).values_list("id", flat=True)
        return Resource.objects.filter(
            Q(owner=user) | Q(plan_id__in=list(accessible_plan_ids))
        ).distinct()

    def perform_update(self, serializer):
        _validate_plan_link(self.request, serializer.validated_data.get("plan", serializer.instance.plan))
        serializer.save()

    def perform_destroy(self, instance):
        if instance.owner_id != self.request.user.id:
            raise PermissionDenied("You can only delete resources you uploaded.")
        instance.delete()
