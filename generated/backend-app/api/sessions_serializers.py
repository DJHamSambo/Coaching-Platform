from rest_framework import serializers
from django.db.models import Q
from api.models import Session, WeeklyAvailabilityWindow, UnavailablePeriod
from api.serializers_utils import validate_ordered_range


def _resolve_actor(serializer: serializers.Serializer):
    request = serializer.context.get("request")
    if request and getattr(request, "user", None) and request.user.is_authenticated:
        return request.user

    instance = getattr(serializer, "instance", None)
    if instance is not None:
        if hasattr(instance, "coach_id"):
            return instance.coach
        if hasattr(instance, "owner_id"):
            return instance.owner

    raise serializers.ValidationError("Unable to resolve authenticated actor for this request.")


def _resolve_actor_for_overlap_check(serializer: serializers.Serializer):
    try:
        return _resolve_actor(serializer)
    except serializers.ValidationError:
        if serializer.instance is not None:
            raise
        return None
    return None


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
        weekday = attrs.get("weekday", getattr(self.instance, "weekday", None))
        coach = _resolve_actor_for_overlap_check(self)

        validate_ordered_range(start_time, end_time, "start_time", "end_time")

        if coach and weekday is not None and start_time and end_time:
            queryset = WeeklyAvailabilityWindow.objects.filter(coach=coach, weekday=weekday)
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            overlaps = queryset.filter(start_time__lt=end_time, end_time__gt=start_time).exists()
            if overlaps:
                raise serializers.ValidationError("Availability window overlaps an existing entry.")

        return attrs


class UnavailablePeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnavailablePeriod
        fields = ["id", "start_at", "end_at", "reason", "coach", "created_at", "updated_at"]
        read_only_fields = ("id", "coach", "created_at", "updated_at")

    def validate(self, attrs):
        start_at = attrs.get("start_at", getattr(self.instance, "start_at", None))
        end_at = attrs.get("end_at", getattr(self.instance, "end_at", None))
        coach = _resolve_actor_for_overlap_check(self)

        validate_ordered_range(start_at, end_at, "start_at", "end_at")

        if coach and start_at and end_at:
            queryset = UnavailablePeriod.objects.filter(coach=coach)
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            overlaps = queryset.filter(Q(start_at__lt=end_at) & Q(end_at__gt=start_at)).exists()
            if overlaps:
                raise serializers.ValidationError("Unavailable period overlaps an existing entry.")

        return attrs
