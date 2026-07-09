from rest_framework import generics, permissions
from django.contrib.auth.models import User
from django.db.models import Q
from api.messages_serializers import MessagesSerializer
from api.models import Coachee, CoachingPlan
from api.notifications import notify_mentions


def _resolve_owner(request) -> User:
    user = request.user
    if user and getattr(user, "is_authenticated", False):
        return user
    owner, _ = User.objects.get_or_create(username="demo_coach", defaults={"email": "demo@example.com"})
    return owner


def _linked_coachee_profiles(user):
    """Coachee profiles linked to this user (FK preferred, legacy name fallback)."""
    by_user = Coachee.objects.filter(user=user)
    if by_user.exists():
        return by_user
    return Coachee.objects.filter(user__isnull=True, name__iexact=user.username)


def _is_coachee_user(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return _linked_coachee_profiles(user).exists()


def _accessible_plan_ids(user):
    """Plan ids the user participates in (as coach or as the assigned coachee)."""
    if _is_coachee_user(user):
        return CoachingPlan.objects.filter(
            coachee__in=_linked_coachee_profiles(user)
        ).values_list("id", flat=True)
    return CoachingPlan.objects.filter(coach=user).values_list("id", flat=True)


class MessagesListView(generics.ListCreateAPIView):
    serializer_class = MessagesSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        user = self.request.user
        model = self.serializer_class.Meta.model
        if user and getattr(user, "is_authenticated", False):
            # A user sees discussions they authored plus every discussion on a
            # plan they participate in (so coach and coachee share a thread).
            plan_ids = list(_accessible_plan_ids(user))
            queryset = model.objects.filter(Q(owner=user) | Q(plan_id__in=plan_ids))
        else:
            queryset = model.objects.filter(owner=_resolve_owner(self.request))
        plan_id = self.request.query_params.get("plan_id")
        task_id = self.request.query_params.get("task_id")
        if plan_id:
            queryset = queryset.filter(plan_id=plan_id)
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        return queryset.order_by("-created_at")


    def perform_create(self, serializer):
        message = serializer.save(owner=_resolve_owner(self.request))
        actor_name = message.author or getattr(self.request.user, "username", "") or ""
        is_action = bool(message.task_id)
        notify_mentions(
            actor_name,
            message.title,
            explicit_mentions=message.mentions,
            area_label="an action discussion" if is_action else "a coaching plan discussion",
            target_type="action" if is_action else "plan",
            target_id=message.task_id if is_action else message.plan_id,
            plan_id=message.plan_id,
            action_id=message.task_id if is_action else None,
        )


class MessagesDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MessagesSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        owner = _resolve_owner(self.request)
        return self.serializer_class.Meta.model.objects.filter(owner=owner)
