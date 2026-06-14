from rest_framework import generics, permissions
from django.contrib.auth.models import User
from api.plans_serializers import CoachingPlanSerializer, CoachingPlanListSerializer, ActionSerializer
from api.models import CoachingPlan, Task


def _resolve_owner(request) -> User:
    user = request.user
    if user and getattr(user, "is_authenticated", False):
        return user
    owner, _ = User.objects.get_or_create(username="demo_coach", defaults={"email": "demo@example.com"})
    return owner


class PlansListView(generics.ListCreateAPIView):
    """List all plans (sorted by target_date) or create a new plan."""
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return CoachingPlanListSerializer
        return CoachingPlanSerializer

    def get_queryset(self):
        return CoachingPlan.objects.filter(coach=_resolve_owner(self.request)).order_by("target_date")

    def perform_create(self, serializer):
        serializer.save(coach=_resolve_owner(self.request))


class PlansDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a single plan (includes nested actions)."""
    serializer_class = CoachingPlanSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return CoachingPlan.objects.filter(coach=_resolve_owner(self.request))


class PlanActionsListView(generics.ListCreateAPIView):
    """List or create actions for a specific coaching plan."""
    serializer_class = ActionSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        plan_id = self.kwargs["plan_id"]
        owner = _resolve_owner(self.request)
        return Task.objects.filter(plan_id=plan_id, owner=owner).order_by("order", "created_at")

    def perform_create(self, serializer):
        plan_id = self.kwargs["plan_id"]
        owner = _resolve_owner(self.request)
        plan = CoachingPlan.objects.get(pk=plan_id, coach=owner)
        # Auto-assign order as next in sequence
        last = Task.objects.filter(plan=plan).order_by("-order").first()
        next_order = (last.order + 1) if last else 0
        serializer.save(plan=plan, owner=owner, order=next_order)


class PlanActionsDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update (including status/order), or delete a single action."""
    serializer_class = ActionSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        plan_id = self.kwargs["plan_id"]
        owner = _resolve_owner(self.request)
        return Task.objects.filter(plan_id=plan_id, owner=owner)
