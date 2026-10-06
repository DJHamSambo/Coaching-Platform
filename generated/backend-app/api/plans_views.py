from django.db.models import Q
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
from django.contrib.auth.models import User
from api.plans_serializers import CoachingPlanSerializer, CoachingPlanListSerializer, ActionSerializer
from api.models import CoachingPlan, Task
from api.notifications import notify, resolve_recipient
from api.relationships import coachee_recipient, coachee_relationships as _linked_coachee_profiles, is_coachee_user as _is_coachee_user


def _resolve_owner(request) -> User:
    user = request.user
    if user and getattr(user, "is_authenticated", False):
        return user
    owner, _ = User.objects.get_or_create(username="demo_coach", defaults={"email": "demo@example.com"})
    return owner


def _is_admin(user) -> bool:
    """Administrators oversee every coach's plans, not just their own.

    Without this the plan queries below filter on ``coach=<the admin>``, so an
    admin could only open plans they happened to create themselves.
    """
    return bool(user and getattr(user, "is_authenticated", False) and user.is_staff)


def _validate_plan_coachee(request, coachee):
    """A coach may only attach a plan to one of their own relationships."""
    if coachee is None or _is_admin(request.user):
        return
    if coachee.added_by_id != _resolve_owner(request).id:
        raise PermissionDenied("You can only assign plans to your own coachees.")


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
        # Coaches can only assign to themselves or the assigned coachee. The
        # plan's own coach is included so an admin acting on someone else's plan
        # can assign to that coach; for a coach it is already their own name.
        coach_user = _resolve_owner(request)
        allowed = {coach_user.username, plan.coach.username}
        if plan.coachee is not None:
            allowed.add(plan.coachee.name)
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
        if _is_admin(self.request.user):
            return CoachingPlan.objects.all().order_by("target_date")
        return CoachingPlan.objects.filter(coach=owner).order_by("target_date")

    def perform_create(self, serializer):
        if _is_coachee_user(self.request.user):
            raise PermissionDenied("Coachees cannot create coaching plans.")
        _validate_plan_coachee(self.request, serializer.validated_data.get("coachee"))
        plan = serializer.save(coach=_resolve_owner(self.request))

        # Notify the assigned coachee that a new plan was created for them
        # (only once they've accepted the relationship).
        coachee = plan.coachee
        recipient = coachee_recipient(coachee)
        if recipient is not None:
            actor_name = getattr(self.request.user, "username", "") or ""
            notify(
                recipient,
                actor_name,
                "plan_assigned",
                f"{actor_name} assigned you a new coaching plan: {plan.title}",
                target_type="plan",
                target_id=plan.id,
                plan_id=plan.id,
            )


class PlansDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a single plan (includes nested actions)."""
    serializer_class = CoachingPlanSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        owner = _resolve_owner(self.request)
        if _is_coachee_user(self.request.user):
            return CoachingPlan.objects.filter(coachee__in=_linked_coachee_profiles(self.request.user))
        if _is_admin(self.request.user):
            return CoachingPlan.objects.all()
        return CoachingPlan.objects.filter(coach=owner)

    def perform_update(self, serializer):
        if _is_coachee_user(self.request.user):
            raise PermissionDenied("Coachees cannot update coaching plans.")
        if "coachee" in serializer.validated_data:
            _validate_plan_coachee(self.request, serializer.validated_data["coachee"])
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
        elif _is_admin(self.request.user):
            plan = CoachingPlan.objects.filter(pk=plan_id).first()
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
        task = serializer.save(plan=plan, owner=coach_owner, order=next_order)

        # Notify the assignee that an action was created and assigned to them.
        actor_name = getattr(self.request.user, "username", "") or ""
        if task.assignee:
            recipient = resolve_recipient(task.assignee)
            notify(
                recipient,
                actor_name,
                "action_created",
                f"{actor_name} assigned you an action on \"{plan.title}\": {task.title}",
                target_type="action",
                target_id=task.id,
                plan_id=plan.id,
                action_id=task.id,
            )


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
        elif _is_admin(self.request.user):
            return Task.objects.filter(plan_id=plan_id)
        else:
            owner = _resolve_owner(self.request)
            return Task.objects.filter(plan_id=plan_id, plan__coach=owner)

    def perform_update(self, serializer):
        instance = self.get_object()
        plan_id = self.kwargs["plan_id"]
        owner = _resolve_owner(self.request)
        if _is_coachee_user(self.request.user) or _is_admin(self.request.user):
            plan = CoachingPlan.objects.get(pk=plan_id)
        else:
            plan = CoachingPlan.objects.get(pk=plan_id, coach=owner)

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
