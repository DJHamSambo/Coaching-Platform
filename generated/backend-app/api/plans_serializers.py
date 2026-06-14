from rest_framework import serializers
from api.models import CoachingPlan, Task, Message


class ActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ["id", "title", "description", "status", "assignee", "order", "due_date", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class PlanMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "title", "author", "mentions", "task_id", "created_at"]
        read_only_fields = ["id", "created_at"]


class CoachingPlanSerializer(serializers.ModelSerializer):
    actions = ActionSerializer(many=True, read_only=True)
    coachee_name = serializers.CharField(source="coachee.name", read_only=True, default=None)

    class Meta:
        model = CoachingPlan
        fields = [
            "id", "title", "description", "goal", "status",
            "target_date", "coachee", "coachee_name", "coach",
            "actions", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "coach", "created_at", "updated_at"]


class CoachingPlanListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for the plan list view (no nested actions)."""
    coachee_name = serializers.CharField(source="coachee.name", read_only=True, default=None)

    class Meta:
        model = CoachingPlan
        fields = ["id", "title", "description", "goal", "status", "target_date", "coachee", "coachee_name", "created_at"]
        read_only_fields = ["id", "created_at"]
