from rest_framework import serializers
from api.models import Resource


class ResourcesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = "__all__"
        read_only_fields = ("id", "owner", "created_at", "updated_at")
