from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q
from api.insights_serializers import InsightsSerializer
from api.models import Insight
from api.notifications import notify_mentions
from api.relationships import (
    active_coachee_relationships,
    coach_relationships,
    coachee_relationships,
    is_coachee_user,
)


def _visible_insights(user):
    if is_coachee_user(user):
        # Coachees see insights from every relationship they've consented to
        # (one per coach) plus their own private reflections.
        return Insight.objects.filter(Q(coachee__in=coachee_relationships(user)) | Q(owner=user))
    # Coaches see insights within their own relationships plus their own notes.
    # Insights a coachee shared from another relationship are served read-only
    # by the coachee's shared-data endpoint, never mixed in here.
    return Insight.objects.filter(Q(coachee__in=coach_relationships(user)) | Q(owner=user))


def _validate_insight_coachee(user, coachee):
    """Stop an insight being filed under someone else's relationship."""
    if coachee is None:
        return
    if is_coachee_user(user):
        if not active_coachee_relationships(user).filter(pk=coachee.pk).exists():
            raise PermissionDenied("You can only add insights to a current coaching relationship.")
    elif coachee.added_by_id != user.id:
        raise PermissionDenied("You can only add insights for your own coachees.")


class InsightsListView(generics.ListCreateAPIView):
    serializer_class = InsightsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = _visible_insights(self.request.user).order_by('-created_at')
        coachee_id = self.request.query_params.get('coachee_id')
        if coachee_id and not is_coachee_user(self.request.user):
            queryset = queryset.filter(coachee_id=coachee_id)
        return queryset

    def perform_create(self, serializer):
        _validate_insight_coachee(self.request.user, serializer.validated_data.get("coachee"))
        insight = serializer.save(owner=self.request.user)
        actor_name = insight.author or getattr(self.request.user, "username", "") or ""
        notify_mentions(
            actor_name,
            insight.title,
            area_label="an insight",
            target_type="insight",
            target_id=insight.id,
        )


class InsightsDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = InsightsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return _visible_insights(self.request.user)

    def perform_update(self, serializer):
        # Only allow users to edit insights they created
        if serializer.instance.owner != self.request.user:
            raise PermissionDenied("You can only edit insights you created.")
        if "coachee" in serializer.validated_data:
            _validate_insight_coachee(self.request.user, serializer.validated_data["coachee"])
        serializer.save()

    def perform_destroy(self, instance):
        # Only allow users to delete insights they created
        if instance.owner != self.request.user:
            raise PermissionDenied("You can only delete insights you created.")
        instance.delete()
