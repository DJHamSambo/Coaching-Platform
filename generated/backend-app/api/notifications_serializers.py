from rest_framework import serializers

from api.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            "id",
            "actor_name",
            "notification_type",
            "message",
            "target_type",
            "target_id",
            "plan_id",
            "action_id",
            "is_read",
            "created_at",
        )
        read_only_fields = (
            "id",
            "actor_name",
            "notification_type",
            "message",
            "target_type",
            "target_id",
            "plan_id",
            "action_id",
            "created_at",
        )
