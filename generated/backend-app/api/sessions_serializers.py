from rest_framework import serializers
from api.models import Session


class SessionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = "__all__"
        read_only_fields = ("id", "owner", "created_at", "updated_at")
