from rest_framework import serializers
from api.models import Insight


class InsightsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Insight
        fields = "__all__"
        read_only_fields = ("id", "owner", "created_at", "updated_at")
