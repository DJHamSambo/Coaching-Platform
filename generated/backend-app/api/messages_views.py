from rest_framework import generics, permissions
from django.contrib.auth.models import User
from api.messages_serializers import MessagesSerializer


def _resolve_owner(request) -> User:
    user = request.user
    if user and getattr(user, "is_authenticated", False):
        return user
    owner, _ = User.objects.get_or_create(username="demo_coach", defaults={"email": "demo@example.com"})
    return owner


class MessagesListView(generics.ListCreateAPIView):
    serializer_class = MessagesSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        owner = _resolve_owner(self.request)
        queryset = self.serializer_class.Meta.model.objects.filter(owner=owner)
        plan_id = self.request.query_params.get("plan_id")
        task_id = self.request.query_params.get("task_id")
        if plan_id:
            queryset = queryset.filter(plan_id=plan_id)
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(owner=_resolve_owner(self.request))


class MessagesDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MessagesSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        owner = _resolve_owner(self.request)
        return self.serializer_class.Meta.model.objects.filter(owner=owner)
