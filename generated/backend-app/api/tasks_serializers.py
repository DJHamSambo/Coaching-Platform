from rest_framework import serializers
from api.models import Task


class TasksSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = "__all__"
        read_only_fields = ("id", "owner", "created_at", "updated_at")
