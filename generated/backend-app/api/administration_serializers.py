from __future__ import annotations

from django.contrib.auth.models import User
from rest_framework import serializers

from api.account_provisioning import add_coachee_for_coach, provision_coach_login
from api.models import Coachee


class CoachSerializer(serializers.ModelSerializer):
    # allow_blank: the Add coach form has no password field and posts an empty
    # string, which DRF rejected as "This field may not be blank" - so creating
    # a coach from the UI always failed. A blank password is meaningful here: it
    # means "provision the account and email an activation link" (see create()).
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    # True/False once an invitation was attempted, null when none was due
    # (a password was supplied). Mirrors AdminCoacheeSerializer so a failed
    # coach invitation cannot be reported to the admin as plain success.
    invitation_sent = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "is_staff", "is_active", "password",
            "invitation_sent",
        ]
        read_only_fields = ["id", "invitation_sent"]

    def get_invitation_sent(self, obj) -> bool | None:
        return getattr(obj, "invitation_sent", None)

    def create(self, validated_data):
        password = validated_data.pop("password", "")
        user = User(**validated_data)
        if password:
            user.set_password(password)
            user.save()
            # No invitation is due: the coach can sign in with this password.
            user.invitation_sent = None
        else:
            # No password supplied: leave the account inactive and email an
            # activation link so the coach sets their own password. No password
            # is ever transmitted.
            user.set_unusable_password()
            user.save()
            user.invitation_sent = provision_coach_login(user)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class AdminCoacheeSerializer(serializers.ModelSerializer):
    added_by_username = serializers.CharField(source="added_by.username", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    user_email = serializers.SerializerMethodField()
    user_phone = serializers.SerializerMethodField()
    request_questionnaire = serializers.BooleanField(write_only=True, required=False, default=True)
    # True/False once an invitation was attempted, null when none was due. Set
    # transiently by provision_coachee_login so the UI can warn that a coachee
    # was created but never emailed, rather than reporting a plain success.
    invitation_sent = serializers.SerializerMethodField()

    class Meta:
        model = Coachee
        fields = [
            "id", "name", "email", "notes", "user", "user_username",
            "user_email", "user_phone", "added_by", "added_by_username", "status",
            "responded_at", "created_at", "request_questionnaire", "invitation_sent",
        ]
        # ``user`` is set only by matching the email server-side; letting a
        # coach write it would let them attach any login to their relationship.
        read_only_fields = [
            "id", "user", "added_by", "added_by_username", "status", "responded_at",
            "created_at", "user_username", "user_email", "user_phone", "invitation_sent",
        ]

    def get_invitation_sent(self, obj) -> bool | None:
        return getattr(obj, "invitation_sent", None)

    def get_user_email(self, obj) -> str:
        return obj.user.email if obj.user_id else ""

    def get_user_phone(self, obj) -> str:
        if not obj.user_id:
            return ""
        profile = getattr(obj.user, "profile", None)
        return profile.phone if profile else ""

    def create(self, validated_data):
        request_questionnaire = validated_data.pop("request_questionnaire", True)
        coach = validated_data.pop("added_by")
        # Matches an existing coachee login by email or provisions a new one,
        # and emails the invitation either way.
        return add_coachee_for_coach(
            super().create, validated_data, coach, request_questionnaire=request_questionnaire
        )


class CoachDirectorySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]
        read_only_fields = ["id", "username", "email"]
