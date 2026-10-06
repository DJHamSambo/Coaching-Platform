from rest_framework import serializers
from api.account_provisioning import add_coachee_for_coach
from api.models import Coachee


class CoacheeSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    # True/False once an invitation was attempted, null when none was due.
    invitation_sent = serializers.SerializerMethodField()

    class Meta:
        model = Coachee
        fields = [
            "id", "name", "email", "notes", "user", "user_username",
            "added_by", "status", "responded_at", "created_at", "invitation_sent",
        ]
        # ``user`` is set only by matching the email server-side; letting a
        # coach write it would let them attach any login to their relationship.
        read_only_fields = [
            "id", "user", "added_by", "status", "responded_at", "created_at",
            "user_username", "invitation_sent",
        ]

    def get_invitation_sent(self, obj) -> bool | None:
        return getattr(obj, "invitation_sent", None)

    def create(self, validated_data):
        coach = validated_data.pop("added_by")
        # Matches an existing coachee login by email or provisions a new one,
        # and emails the invitation either way.
        return add_coachee_for_coach(super().create, validated_data, coach)
