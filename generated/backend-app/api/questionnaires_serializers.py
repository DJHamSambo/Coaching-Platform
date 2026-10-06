from rest_framework import serializers

from api.models import FoundationalQuestionnaire


class FoundationalQuestionnaireSerializer(serializers.ModelSerializer):
    coach_username = serializers.CharField(source="coachee.added_by.username", read_only=True, default=None)

    class Meta:
        model = FoundationalQuestionnaire
        fields = ["id", "name", "answers", "coachee", "coach_username", "submitted_at"]
        read_only_fields = ("id", "coach_username", "submitted_at")
        extra_kwargs = {"coachee": {"required": False, "allow_null": True}}

    def validate_answers(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Answers must be a list of entries.")
        for item in value:
            if not isinstance(item, dict) or "question" not in item or "answer" not in item:
                raise serializers.ValidationError(
                    "Each answer entry must include a 'question' and an 'answer'."
                )
        return value
