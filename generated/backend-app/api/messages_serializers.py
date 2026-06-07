from rest_framework import serializers
from api.models import Message


class MessagesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = "__all__"
        read_only_fields = ("id", "owner", "created_at", "updated_at")
