from rest_framework import generics, permissions
from django.contrib.auth.models import User
from api.tasks_serializers import TasksSerializer


def _resolve_owner(request) -> User:
    user = request.user
    if user and getattr(user, "is_authenticated", False):
        return user
    owner, _ = User.objects.get_or_create(username="demo_coach", defaults={"email": "demo@example.com"})
    return owner


class TasksListView(generics.ListCreateAPIView):
    serializer_class = TasksSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        owner = _resolve_owner(self.request)
        return self.serializer_class.Meta.model.objects.filter(owner=owner).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(owner=_resolve_owner(self.request))


class TasksDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TasksSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        owner = _resolve_owner(self.request)
        return self.serializer_class.Meta.model.objects.filter(owner=owner)
