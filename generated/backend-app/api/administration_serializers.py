from __future__ import annotations

from django.contrib.auth.models import User
from rest_framework import serializers

from api.account_provisioning import provision_coach_login, provision_coachee_login
from api.models import Coachee


class CoachSerializer(serializers.ModelSerializer):
    # allow_blank: the Add coach form has no password field and posts an empty
    # string, which DRF rejected as "This field may not be blank" - so creating
    # a coach from the UI always failed. A blank password is meaningful here: it
    # means "provision the account and email an activation link" (see create()).
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "is_staff", "is_active", "password"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        password = validated_data.pop("password", "")
        user = User(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        else:
            # No password supplied: leave the account inactive and email an
            # activation link so the coach sets their own password. No password
            # is ever transmitted.
            user.set_unusable_password()
            user.save()
            provision_coach_login(user)
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
            "user_email", "user_phone", "added_by", "added_by_username", "created_at",
            "request_questionnaire", "invitation_sent",
        ]
        read_only_fields = [
            "id", "added_by", "added_by_username", "created_at",
            "user_username", "user_email", "user_phone", "invitation_sent",
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
        coachee = super().create(validated_data)
        # Provision a login account + welcome email when an email is provided.
        provision_coachee_login(coachee, request_questionnaire=request_questionnaire)
        return coachee


class CoachDirectorySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]
        read_only_fields = ["id", "username", "email"]
