from rest_framework import serializers

from api.models import CoachingContract


class CoachingContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoachingContract
        fields = ["id", "title", "data", "created_at"]
        read_only_fields = ("id", "created_at")

    def validate_data(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Contract data must be an object.")
        return value
