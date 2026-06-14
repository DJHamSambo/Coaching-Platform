from rest_framework import serializers
from api.models import Coachee


class CoacheeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coachee
        fields = ["id", "name", "email", "notes", "added_by", "created_at"]
        read_only_fields = ["id", "added_by", "created_at"]
