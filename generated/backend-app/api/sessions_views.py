from rest_framework import generics, permissions
from api.sessions_serializers import SessionsSerializer, WeeklyAvailabilityWindowSerializer, UnavailablePeriodSerializer
from api.models import WeeklyAvailabilityWindow, UnavailablePeriod


class SessionsListView(generics.ListCreateAPIView):
    serializer_class = SessionsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.serializer_class.Meta.model.objects.filter(owner=self.request.user).select_related("coachee").order_by("date")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class SessionsDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SessionsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.serializer_class.Meta.model.objects.filter(owner=self.request.user).select_related("coachee")


class WeeklyAvailabilityWindowListView(generics.ListCreateAPIView):
    serializer_class = WeeklyAvailabilityWindowSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WeeklyAvailabilityWindow.objects.filter(coach=self.request.user).order_by("weekday", "start_time")

    def perform_create(self, serializer):
        serializer.save(coach=self.request.user)


class WeeklyAvailabilityWindowDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WeeklyAvailabilityWindowSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WeeklyAvailabilityWindow.objects.filter(coach=self.request.user)


class UnavailablePeriodListView(generics.ListCreateAPIView):
    serializer_class = UnavailablePeriodSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UnavailablePeriod.objects.filter(coach=self.request.user).order_by("start_at")

    def perform_create(self, serializer):
        serializer.save(coach=self.request.user)


class UnavailablePeriodDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UnavailablePeriodSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UnavailablePeriod.objects.filter(coach=self.request.user)
