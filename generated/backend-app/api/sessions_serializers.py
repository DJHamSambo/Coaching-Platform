from rest_framework import serializers
from api.models import Session, WeeklyAvailabilityWindow, UnavailablePeriod


class SessionsSerializer(serializers.ModelSerializer):
    coachee_name = serializers.SerializerMethodField()

    class Meta:
        model = Session
        fields = [
            "id",
            "title",
            "date",
            "duration_minutes",
            "coachee",
            "coachee_name",
            "notes",
            "mode",
            "requested_by",
            "owner",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "owner", "created_at", "updated_at", "coachee_name")

    def get_coachee_name(self, obj):
        return obj.coachee.name if obj.coachee else ""


class WeeklyAvailabilityWindowSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklyAvailabilityWindow
        fields = ["id", "weekday", "start_time", "end_time", "coach", "created_at", "updated_at"]
        read_only_fields = ("id", "coach", "created_at", "updated_at")

    def validate(self, attrs):
        start_time = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError("start_time must be earlier than end_time")
        return attrs


class UnavailablePeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnavailablePeriod
        fields = ["id", "start_at", "end_at", "reason", "coach", "created_at", "updated_at"]
        read_only_fields = ("id", "coach", "created_at", "updated_at")

    def validate(self, attrs):
        start_at = attrs.get("start_at", getattr(self.instance, "start_at", None))
        end_at = attrs.get("end_at", getattr(self.instance, "end_at", None))
        if start_at and end_at and start_at >= end_at:
            raise serializers.ValidationError("start_at must be earlier than end_at")
        return attrs
