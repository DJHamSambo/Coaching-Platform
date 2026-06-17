from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, permissions, pagination
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import Coachee, Message, Session, WeeklyAvailabilityWindow, UnavailablePeriod
from api.permissions import OwnsObjectPermission
from api.sessions_serializers import SessionsSerializer, WeeklyAvailabilityWindowSerializer, UnavailablePeriodSerializer
from api.administration_serializers import CoachDirectorySerializer


class CalendarPageNumberPagination(pagination.PageNumberPagination):
    page_size = getattr(settings, "CALENDAR_PAGE_SIZE", 100)
    page_size_query_param = "page_size"
    max_page_size = getattr(settings, "CALENDAR_MAX_PAGE_SIZE", 500)


def _coachee_identity_filter(user) -> Q:
    lookup = Q(user=user) | Q(name__iexact=user.username)
    if user.email:
        lookup |= Q(email__iexact=user.email)
    return lookup


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
            return Session.objects.filter(coachee__in=_linked_coachee_queryset(self.request.user)).select_related("coachee", "owner").order_by("date")
        return Session.objects.filter(owner=self.request.user).select_related("coachee").order_by("date")

    def perform_create(self, serializer):
        if _is_coachee_user(self.request.user):
            coach, coachee_profile = _resolve_selected_coach_for_coachee(self.request)
            start_at = serializer.validated_data.get("date")
            duration = serializer.validated_data.get("duration_minutes", 60)
            _validate_request_within_coach_availability(coach, start_at, duration)
            created = serializer.save(
                owner=coach,
                coachee=coachee_profile,
                requested_by="coachee",
                status="requested",
            )
            Message.objects.create(
                title=f"Session request from {self.request.user.username}: {created.title}",
                owner=coach,
                author=self.request.user.username,
                plan=None,
                task_id=None,
                mentions="",
            )
            return

        serializer.save(owner=self.request.user, requested_by="coach", status=serializer.validated_data.get("status", "accepted"))


class SessionsDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SessionsSerializer
    permission_classes = [permissions.IsAuthenticated, OwnsObjectPermission]

    def get_queryset(self):
        if _is_coachee_user(self.request.user):
            return Session.objects.filter(coachee__in=_linked_coachee_queryset(self.request.user)).select_related("coachee", "owner")
        return Session.objects.filter(owner=self.request.user).select_related("coachee")

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.owner_id != self.request.user.id:
            raise PermissionDenied("Coachees cannot update sessions. Coaches review requests.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.owner_id != self.request.user.id:
            raise PermissionDenied("Coachees cannot delete sessions.")
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
