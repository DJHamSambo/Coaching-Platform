from rest_framework import serializers

from api.models import FoundationalQuestionnaire


class FoundationalQuestionnaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoundationalQuestionnaire
        fields = ["id", "name", "answers", "submitted_at"]
        read_only_fields = ("id", "submitted_at")

    def validate_answers(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Answers must be a list of entries.")
        for item in value:
            if not isinstance(item, dict) or "question" not in item or "answer" not in item:
                raise serializers.ValidationError(
                    "Each answer entry must include a 'question' and an 'answer'."
                )
        return value
