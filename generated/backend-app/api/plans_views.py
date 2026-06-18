from django.db.models import Q
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
from django.contrib.auth.models import User
from api.plans_serializers import CoachingPlanSerializer, CoachingPlanListSerializer, ActionSerializer
from api.models import Coachee, CoachingPlan, Task


def _resolve_owner(request) -> User:
    user = request.user
    if user and getattr(user, "is_authenticated", False):
        return user
    owner, _ = User.objects.get_or_create(username="demo_coach", defaults={"email": "demo@example.com"})
    return owner


def _is_coachee_user(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    # Prefer FK link; fall back only for legacy coachees without a linked user
    return (
        Coachee.objects.filter(user=user).exists()
        or Coachee.objects.filter(user__isnull=True, name__iexact=user.username).exists()
    )


def _linked_coachee_profiles(user):
    if not user or not getattr(user, "is_authenticated", False):
        return Coachee.objects.none()
    # Prefer FK link; fall back only for legacy coachees without a linked user
    by_user = Coachee.objects.filter(user=user)
    if by_user.exists():
        return by_user
    return Coachee.objects.filter(user__isnull=True, name__iexact=user.username)


def _validate_action_assignee(request, plan, assignee_name):
    """Validate that the assignee is allowed based on user role and plan assignment."""
    if not assignee_name:
        return
    
    if _is_coachee_user(request.user):
        # Coachees can only assign to themselves or the coach who assigned the plan
        allowed = {request.user.username, plan.coach.username}
        if assignee_name not in allowed:
            raise PermissionDenied("Coachees can only assign actions to themselves or their coach.")
    else:
        # Coaches can only assign to themselves or the assigned coachee
        coach_user = _resolve_owner(request)
        allowed = {coach_user.username, plan.coachee.name}
        if assignee_name not in allowed:
            raise PermissionDenied("Coaches can only assign actions to themselves or the assigned coachee.")


class PlansListView(generics.ListCreateAPIView):
    """List all plans (sorted by target_date) or create a new plan."""
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return CoachingPlanListSerializer
        return CoachingPlanSerializer

    def get_queryset(self):
        owner = _resolve_owner(self.request)
        if _is_coachee_user(self.request.user):
            return CoachingPlan.objects.filter(coachee__in=_linked_coachee_profiles(self.request.user)).order_by("target_date")
        return CoachingPlan.objects.filter(coach=owner).order_by("target_date")

    def perform_create(self, serializer):
        if _is_coachee_user(self.request.user):
            raise PermissionDenied("Coachees cannot create coaching plans.")
        serializer.save(coach=_resolve_owner(self.request))


class PlansDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a single plan (includes nested actions)."""
    serializer_class = CoachingPlanSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        owner = _resolve_owner(self.request)
        if _is_coachee_user(self.request.user):
            return CoachingPlan.objects.filter(coachee__in=_linked_coachee_profiles(self.request.user))
        return CoachingPlan.objects.filter(coach=owner)

    def perform_update(self, serializer):
        if _is_coachee_user(self.request.user):
            raise PermissionDenied("Coachees cannot update coaching plans.")
        serializer.save()

    def perform_destroy(self, instance):
        if _is_coachee_user(self.request.user):
            raise PermissionDenied("Coachees cannot delete coaching plans.")
        instance.delete()


class PlanActionsListView(generics.ListCreateAPIView):
    """List or create actions for a specific coaching plan."""
    serializer_class = ActionSerializer
    permission_classes = [permissions.AllowAny]

    def _get_accessible_plan(self):
        plan_id = self.kwargs["plan_id"]
        if _is_coachee_user(self.request.user):
            plan = CoachingPlan.objects.filter(
                pk=plan_id,
                coachee__in=_linked_coachee_profiles(self.request.user)
            ).first()
        else:
            owner = _resolve_owner(self.request)
            plan = CoachingPlan.objects.filter(pk=plan_id, coach=owner).first()
        if not plan:
            raise PermissionDenied("You do not have access to this plan.")
        return plan

    def get_queryset(self):
        plan = self._get_accessible_plan()
        return Task.objects.filter(plan_id=plan.id).order_by("order", "created_at")

    def perform_create(self, serializer):
        plan = self._get_accessible_plan()
        coach_owner = plan.coach
        # Validate assignee if provided
        assignee = serializer.validated_data.get("assignee")
        if assignee:
            _validate_action_assignee(self.request, plan, assignee)
        # Auto-assign order as next in sequence
        last = Task.objects.filter(plan=plan).order_by("-order").first()
        next_order = (last.order + 1) if last else 0
        serializer.save(plan=plan, owner=coach_owner, order=next_order)


class PlanActionsDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update (including status/order), or delete a single action."""
    serializer_class = ActionSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        plan_id = self.kwargs["plan_id"]
        if _is_coachee_user(self.request.user):
            plan = CoachingPlan.objects.filter(
                pk=plan_id,
                coachee__in=_linked_coachee_profiles(self.request.user)
            ).first()
            if not plan:
                return Task.objects.none()
            return Task.objects.filter(plan_id=plan.id)
        else:
            owner = _resolve_owner(self.request)
            return Task.objects.filter(plan_id=plan_id, plan__coach=owner)

    def perform_update(self, serializer):
        instance = self.get_object()
        plan_id = self.kwargs["plan_id"]
        owner = _resolve_owner(self.request)
        plan = CoachingPlan.objects.get(pk=plan_id) if _is_coachee_user(self.request.user) else CoachingPlan.objects.get(pk=plan_id, coach=owner)
        
        if _is_coachee_user(self.request.user):
            # Coachees can only update status for now (no reassignment)
            if "status" not in self.request.data or len(self.request.data) > 1:
                raise PermissionDenied("Coachees can only update action status.")
        else:
            # Coaches can update assignee, validate if provided
            assignee = self.request.data.get("assignee")
            if assignee:
                _validate_action_assignee(self.request, plan, assignee)
        
        serializer.save()

    def perform_destroy(self, instance):
        if _is_coachee_user(self.request.user):
            raise PermissionDenied("Coachees cannot delete actions.")
        instance.delete()
