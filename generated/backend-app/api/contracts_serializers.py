from rest_framework import serializers

from api.models import CoachingContract


class CoachingContractSerializer(serializers.ModelSerializer):
    coach_username = serializers.CharField(source="coach.username", read_only=True, default=None)
    coachee_name = serializers.CharField(source="coachee.name", read_only=True, default=None)
    coachee_username = serializers.CharField(source="coachee.user.username", read_only=True, default=None)

    class Meta:
        model = CoachingContract
        fields = [
            "id", "title", "data", "status", "coachee_accepted_terms",
            "coach_username", "coachee", "coachee_name", "coachee_username",
            "created_at", "updated_at",
        ]
        read_only_fields = (
            "id", "status", "coach_username", "coachee_name", "coachee_username",
            "created_at", "updated_at",
        )

    def validate_data(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Contract data must be an object.")
        return value

    def validate_coachee(self, coachee):
        if coachee is None:
            return coachee
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is not None and coachee.added_by_id != user.id:
            raise serializers.ValidationError("You can only assign a coachee you manage.")
        if not coachee.user_id:
            raise serializers.ValidationError(
                "This coachee does not have a linked login yet and cannot sign a contract."
            )
        return coachee
