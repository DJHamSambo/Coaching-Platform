from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, permissions, pagination
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import Coachee, CoachingPlan, Message, Session, WeeklyAvailabilityWindow, UnavailablePeriod
from api.notifications import notify
from api.permissions import OwnsObjectPermission
from api.sessions_serializers import SessionsSerializer, WeeklyAvailabilityWindowSerializer, UnavailablePeriodSerializer
from api.administration_serializers import CoachDirectorySerializer


COACHEE_REQUEST_TITLES = {
    "Goal Setting Session",
    "Momentum Session",
    "Ad hoc Coaching Session",
}


class CalendarPageNumberPagination(pagination.PageNumberPagination):
    page_size = getattr(settings, "CALENDAR_PAGE_SIZE", 100)
    page_size_query_param = "page_size"
    max_page_size = getattr(settings, "CALENDAR_MAX_PAGE_SIZE", 500)


def _coachee_identity_filter(user) -> Q:
    # Prefer FK link; fall back only for legacy coachees without a linked user
    by_user = Q(user=user)
    legacy = Q(user__isnull=True, name__iexact=user.username)
    return by_user | legacy


def _linked_coachee_queryset(user):
    return Coachee.objects.filter(_coachee_identity_filter(user)).select_related("added_by")


def _is_coachee_user(user) -> bool:
    return _linked_coachee_queryset(user).exists()


def _resolve_selected_coach_for_coachee(request):
    coach_id_raw = request.query_params.get("coach_id") or request.data.get("coach_id")
    if not coach_id_raw:
        raise ValidationError({"coach_id": "coach_id is required for coachee calendar requests."})
    try:
        coach_id = int(coach_id_raw)
    except (TypeError, ValueError):
        raise ValidationError({"coach_id": "coach_id must be an integer."})

    coachee_profile = _linked_coachee_queryset(request.user).filter(added_by_id=coach_id).first()
    if not coachee_profile:
        raise PermissionDenied("Selected coach is not linked to this coachee account.")

    return coachee_profile.added_by, coachee_profile


def _validate_request_within_coach_availability(coach, start_at, duration_minutes):
    if not start_at:
        raise ValidationError({"date": "Session request date/time is required."})

    start_local = timezone.localtime(start_at)
    end_local = start_local + timedelta(minutes=max(15, duration_minutes or 60))
    weekday = start_local.weekday()

    has_window = WeeklyAvailabilityWindow.objects.filter(
        coach=coach,
        weekday=weekday,
        start_time__lt=end_local.time(),
        end_time__gt=start_local.time(),
    ).exists()
    if not has_window:
        raise ValidationError({"date": "Requested time is outside the selected coach's availability."})

    has_block = UnavailablePeriod.objects.filter(
        coach=coach,
        start_at__lt=end_local,
        end_at__gt=start_local,
    ).exists()
    if has_block:
        raise ValidationError({"date": "Requested time overlaps an unavailable period for the selected coach."})


def _to_aware_datetime(value):
    if value is None:
        return None
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def _validate_session_not_in_past(value):
    session_at = _to_aware_datetime(value)
    if session_at is None:
        raise ValidationError({"date": "Session date/time is required."})
    if session_at < timezone.now():
        raise ValidationError({"date": "Session date/time cannot be in the past."})


def _resolve_coaching_plan(request, coachee_obj_or_id):
    """Resolve and validate the optional coaching_plan_id from the request."""
    plan_id_raw = request.data.get("coaching_plan_id") or request.data.get("coaching_plan")
    if not plan_id_raw:
        return None
    try:
        plan_id = int(plan_id_raw)
    except (TypeError, ValueError):
        raise ValidationError({"coaching_plan_id": "coaching_plan_id must be an integer."})

    plan = CoachingPlan.objects.filter(pk=plan_id, status__in=["todo", "in_progress"]).first()
    if not plan:
        raise ValidationError({"coaching_plan_id": "Coaching plan not found or not in an active status."})

    # Verify the plan belongs to the relevant coachee
    if coachee_obj_or_id is not None:
        coachee_id = coachee_obj_or_id.pk if hasattr(coachee_obj_or_id, "pk") else (coachee_obj_or_id.id if hasattr(coachee_obj_or_id, "id") else None)
        if coachee_id and plan.coachee_id != coachee_id:
            raise ValidationError({"coaching_plan_id": "Coaching plan does not belong to the selected coachee."})

    return plan


class CoachOwnedListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, OwnsObjectPermission]
    pagination_class = CalendarPageNumberPagination
    owner_field = "coach"

    def get_queryset(self):
        if _is_coachee_user(self.request.user):
            coach, _ = _resolve_selected_coach_for_coachee(self.request)
            return self.model.objects.filter(**{self.owner_field: coach})
        return self.model.objects.filter(**{self.owner_field: self.request.user})

    def perform_create(self, serializer):
        if _is_coachee_user(self.request.user):
            raise PermissionDenied("Coachees cannot modify coach availability.")
        serializer.save(**{self.owner_field: self.request.user})


class CoachOwnedDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, OwnsObjectPermission]
    owner_field = "coach"

    def get_queryset(self):
        return self.model.objects.filter(**{self.owner_field: self.request.user})

    def perform_update(self, serializer):
        if _is_coachee_user(self.request.user):
            raise PermissionDenied("Coachees cannot modify coach availability.")
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        if _is_coachee_user(self.request.user):
            raise PermissionDenied("Coachees cannot modify coach availability.")
        super().perform_destroy(instance)


class SessionsListView(generics.ListCreateAPIView):
    serializer_class = SessionsSerializer
    permission_classes = [permissions.IsAuthenticated, OwnsObjectPermission]
    pagination_class = CalendarPageNumberPagination

    def get_queryset(self):
        if _is_coachee_user(self.request.user):
            qs = Session.objects.filter(coachee__in=_linked_coachee_queryset(self.request.user)).select_related("coachee", "owner", "coaching_plan").order_by("date")
        else:
            qs = Session.objects.filter(owner=self.request.user).select_related("coachee", "coaching_plan").order_by("date")

        plan_id = self.request.query_params.get("coaching_plan_id")
        if plan_id:
            try:
                qs = qs.filter(coaching_plan_id=int(plan_id))
            except (TypeError, ValueError):
                pass
        return qs

    def perform_create(self, serializer):
        start_at = serializer.validated_data.get("date")
        _validate_session_not_in_past(start_at)

        if _is_coachee_user(self.request.user):
            coach, coachee_profile = _resolve_selected_coach_for_coachee(self.request)
            duration = serializer.validated_data.get("duration_minutes", 60)
            title = serializer.validated_data.get("title", "")
            if title not in COACHEE_REQUEST_TITLES:
                raise ValidationError({"title": "Choose one of: Goal Setting Session, Momentum Session, Ad hoc Coaching Session."})
            _validate_request_within_coach_availability(coach, start_at, duration)
            coaching_plan = _resolve_coaching_plan(self.request, coachee_profile)
            created = serializer.save(
                owner=coach,
                coachee=coachee_profile,
                requested_by="coachee",
                coaching_plan=coaching_plan,
            )
            Message.objects.create(
                title=f"Session request from {self.request.user.username}: {created.title}",
                owner=coach,
                author=self.request.user.username,
                plan=None,
                task_id=None,
                mentions="",
            )
            notify(
                coach,
                self.request.user.username,
                "session_booked",
                f"{self.request.user.username} booked a session with you: {created.title}",
                target_type="session",
                target_id=created.id,
                plan_id=coaching_plan.id if coaching_plan else None,
            )
            return

        # Coach creating session
        coachee_id = serializer.validated_data.get("coachee")
        coaching_plan = _resolve_coaching_plan(self.request, coachee_id)
        serializer.save(owner=self.request.user, requested_by="coach", coaching_plan=coaching_plan)


class SessionsDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SessionsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if _is_coachee_user(self.request.user):
            return Session.objects.filter(coachee__in=_linked_coachee_queryset(self.request.user)).select_related("coachee", "owner")
        return Session.objects.filter(owner=self.request.user).select_related("coachee")

    def perform_update(self, serializer):
        instance = self.get_object()
        instance_date = _to_aware_datetime(instance.date)
        if instance_date and instance_date < timezone.now():
            raise ValidationError({"date": "Past sessions cannot be edited."})

        next_date = serializer.validated_data.get("date", instance.date)
        _validate_session_not_in_past(next_date)

        if _is_coachee_user(self.request.user):
            linked_ids = _linked_coachee_queryset(self.request.user).values_list("id", flat=True)
            if instance.coachee_id not in linked_ids:
                raise PermissionDenied("You cannot edit this session.")

            title = serializer.validated_data.get("title", instance.title)
            if title not in COACHEE_REQUEST_TITLES:
                raise ValidationError({"title": "Choose one of: Goal Setting Session, Momentum Session, Ad hoc Coaching Session."})
            serializer.save()
            return

        if instance.owner_id != self.request.user.id:
            raise PermissionDenied("You cannot edit this session.")
        serializer.save()

    def perform_destroy(self, instance):
        instance_date = _to_aware_datetime(instance.date)
        if instance_date and instance_date < timezone.now():
            raise ValidationError({"date": "Past sessions cannot be cancelled."})

        if _is_coachee_user(self.request.user):
            linked_ids = _linked_coachee_queryset(self.request.user).values_list("id", flat=True)
            if instance.coachee_id not in linked_ids:
                raise PermissionDenied("You cannot cancel this session.")
            instance.delete()
            return

        if instance.owner_id != self.request.user.id:
            raise PermissionDenied("You cannot cancel this session.")
        instance.delete()


class WeeklyAvailabilityWindowListView(CoachOwnedListCreateView):
    model = WeeklyAvailabilityWindow
    serializer_class = WeeklyAvailabilityWindowSerializer

    def get_queryset(self):
        return super().get_queryset().order_by("weekday", "start_time")


class WeeklyAvailabilityWindowDetailView(CoachOwnedDetailView):
    model = WeeklyAvailabilityWindow
    serializer_class = WeeklyAvailabilityWindowSerializer


class UnavailablePeriodListView(CoachOwnedListCreateView):
    model = UnavailablePeriod
    serializer_class = UnavailablePeriodSerializer

    def get_queryset(self):
        return super().get_queryset().order_by("start_at")


class UnavailablePeriodDetailView(CoachOwnedDetailView):
    model = UnavailablePeriod
    serializer_class = UnavailablePeriodSerializer


class MyCalendarCoachesListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        linked = _linked_coachee_queryset(request.user)
        coach_ids = linked.values_list("added_by_id", flat=True).distinct()
        coaches = User.objects.filter(id__in=coach_ids, is_active=True).order_by("username")
        return Response(CoachDirectorySerializer(coaches, many=True).data)
