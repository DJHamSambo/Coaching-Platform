from rest_framework import serializers
from api.models import Coachee


class CoacheeSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Coachee
        fields = ["id", "name", "email", "notes", "user", "user_username", "added_by", "created_at"]
        read_only_fields = ["id", "added_by", "created_at", "user_username"]
