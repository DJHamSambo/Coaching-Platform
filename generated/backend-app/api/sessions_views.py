from rest_framework import generics, permissions, pagination
from api.sessions_serializers import SessionsSerializer, WeeklyAvailabilityWindowSerializer, UnavailablePeriodSerializer
from api.models import Session, WeeklyAvailabilityWindow, UnavailablePeriod


class CalendarPageNumberPagination(pagination.PageNumberPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500


class OwnsObjectPermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, "owner"):
            return obj.owner_id == request.user.id
        if hasattr(obj, "coach"):
            return obj.coach_id == request.user.id
        return False


class CoachOwnedListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, OwnsObjectPermission]
    pagination_class = CalendarPageNumberPagination
    owner_field = "coach"

    def get_queryset(self):
        return self.model.objects.filter(**{self.owner_field: self.request.user})

    def perform_create(self, serializer):
        serializer.save(**{self.owner_field: self.request.user})


class CoachOwnedDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, OwnsObjectPermission]
    owner_field = "coach"

    def get_queryset(self):
        return self.model.objects.filter(**{self.owner_field: self.request.user})


class SessionsListView(generics.ListCreateAPIView):
    serializer_class = SessionsSerializer
    permission_classes = [permissions.IsAuthenticated, OwnsObjectPermission]
    pagination_class = CalendarPageNumberPagination

    def get_queryset(self):
        return Session.objects.filter(owner=self.request.user).select_related("coachee").order_by("date")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class SessionsDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SessionsSerializer
    permission_classes = [permissions.IsAuthenticated, OwnsObjectPermission]

    def get_queryset(self):
        return Session.objects.filter(owner=self.request.user).select_related("coachee")


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
