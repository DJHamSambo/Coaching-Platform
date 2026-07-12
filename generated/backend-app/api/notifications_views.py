from rest_framework import generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from api.models import Notification
from api.notifications_serializers import NotificationSerializer


class NotificationsListView(generics.ListAPIView):
    """List the current user's notifications, most recent first."""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Notification.objects.filter(recipient=self.request.user)
        if self.request.query_params.get("unread") in ("1", "true", "True"):
            queryset = queryset.filter(is_read=False)
        return queryset.order_by("-created_at")


class NotificationsDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, mark as read (PATCH is_read), or delete a notification."""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_all_read(request: Request) -> Response:
    updated = Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return Response({"updated": updated})
