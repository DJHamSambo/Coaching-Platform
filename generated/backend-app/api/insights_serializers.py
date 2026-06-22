from rest_framework import serializers
from api.models import Insight


class InsightsSerializer(serializers.ModelSerializer):
    coachee_name = serializers.CharField(source="coachee.name", read_only=True, allow_null=True)

    class Meta:
        model = Insight
        fields = "__all__"
        read_only_fields = ("id", "owner", "created_at", "updated_at")
