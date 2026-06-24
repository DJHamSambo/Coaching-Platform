from __future__ import annotations

from django.contrib.auth.models import User
from rest_framework import serializers

from api.account_provisioning import provision_coach_login, provision_coachee_login
from api.models import Coachee


class CoachSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)

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
            # No password supplied: provision a temporary one and email a
            # welcome message; the coach must reset it on first sign-in.
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

    class Meta:
        model = Coachee
        fields = ["id", "name", "email", "notes", "user", "user_username", "added_by", "added_by_username", "created_at"]
        read_only_fields = ["id", "added_by", "added_by_username", "created_at", "user_username"]

    def create(self, validated_data):
        coachee = super().create(validated_data)
        # Provision a login account + welcome email when an email is provided.
        provision_coachee_login(coachee)
        return coachee


class CoachDirectorySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]
        read_only_fields = ["id", "username", "email"]
