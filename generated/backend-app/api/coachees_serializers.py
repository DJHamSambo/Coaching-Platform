from rest_framework import serializers
from api.account_provisioning import provision_coachee_login
from api.models import Coachee


class CoacheeSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    # True/False once an invitation was attempted, null when none was due.
    invitation_sent = serializers.SerializerMethodField()

    class Meta:
        model = Coachee
        fields = [
            "id", "name", "email", "notes", "user", "user_username",
            "added_by", "created_at", "invitation_sent",
        ]
        read_only_fields = ["id", "added_by", "created_at", "user_username", "invitation_sent"]

    def get_invitation_sent(self, obj) -> bool | None:
        return getattr(obj, "invitation_sent", None)

    def create(self, validated_data):
        coachee = super().create(validated_data)
        # Provision a login account + activation email when an email is provided.
        provision_coachee_login(coachee)
        return coachee
