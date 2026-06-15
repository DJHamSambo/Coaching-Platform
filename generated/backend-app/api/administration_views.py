from __future__ import annotations

from django.contrib.auth.models import User
from rest_framework import generics, permissions

from api.administration_serializers import AdminCoacheeSerializer, CoachDirectorySerializer, CoachSerializer
from api.models import Coachee


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class CoachesListView(generics.ListCreateAPIView):
    serializer_class = CoachSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        return User.objects.order_by("username")


class CoachesDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CoachSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        return User.objects.order_by("username")


class AdminCoacheesListView(generics.ListCreateAPIView):
    serializer_class = AdminCoacheeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Coachee.objects.select_related("added_by").order_by("name")
        return Coachee.objects.select_related("added_by").filter(added_by=self.request.user).order_by("name")

    def perform_create(self, serializer):
        serializer.save(added_by=self.request.user)


class AdminCoacheesDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AdminCoacheeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Coachee.objects.select_related("added_by")
        return Coachee.objects.select_related("added_by").filter(added_by=self.request.user)


class CoachDirectoryListView(generics.ListAPIView):
    serializer_class = CoachDirectorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return User.objects.filter(is_active=True, is_staff=False).order_by("username")
