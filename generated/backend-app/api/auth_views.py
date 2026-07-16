from __future__ import annotations

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from api.account_provisioning import mark_must_reset_password
from api.models import Coachee, UserProfile


class EmailOrUsernameTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Allow signing in with either a username or an email address.

    Provisioned coachee/coach accounts get an auto-generated username they
    never see, so users naturally try their email. If the supplied login looks
    like an email, resolve it to the matching account's username before the
    standard credential check runs.
    """

    def validate(self, attrs):
        login = attrs.get(self.username_field, "")
        if login and "@" in login:
            match = (
                User.objects.filter(email__iexact=login.strip())
                .order_by("id")
                .first()
            )
            if match is not None:
                attrs[self.username_field] = match.username
        return super().validate(attrs)


class EmailOrUsernameTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailOrUsernameTokenObtainPairSerializer


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request: Request) -> Response:
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "").strip()
    email = request.data.get("email", "").strip()

    if not username or not password:
        return Response({"error": "username and password are required"}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(username=username).exists():
        return Response({"error": "username already taken"}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, password=password, email=email)
    return Response({"id": user.pk, "username": user.username}, status=status.HTTP_201_CREATED)


def _me_payload(user, request: Request) -> dict:
    # Prefer FK link; only fall back to name for legacy coachees with no linked user account
    has_coachee_profile = (
        Coachee.objects.filter(user=user).exists()
        or Coachee.objects.filter(user__isnull=True, name__iexact=user.username).exists()
    )

    role = "admin" if user.is_staff else ("coachee" if has_coachee_profile else "coach")
    profile = UserProfile.objects.filter(user=user).first()
    must_reset = bool(profile and profile.must_reset_password)

    avatar_url = None
    if profile and profile.avatar:
        url = profile.avatar.url
        avatar_url = request.build_absolute_uri(url) if request else url

    return {
        "id": user.pk,
        "username": user.username,
        "email": user.email,
        "is_admin": bool(user.is_staff),
        "role": role,
        "must_reset_password": must_reset,
        "avatar_url": avatar_url,
        "phone": profile.phone if profile else "",
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request: Request) -> Response:
    return Response(_me_payload(request.user, request))


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def profile(request: Request) -> Response:
    """View or update the signed-in user's editable profile fields.

    Supports updating the username and uploading a profile picture. Send a
    multipart/form-data request with an optional ``username`` field and/or an
    ``avatar`` file. Returns the same payload as ``/api/auth/me/``.
    """
    user = request.user
    if request.method == "GET":
        return Response(_me_payload(user, request))

    profile_obj, _ = UserProfile.objects.get_or_create(user=user)

    new_username = request.data.get("username")
    if new_username is not None:
        new_username = str(new_username).strip()
        if not new_username:
            return Response(
                {"username": ["Username cannot be empty."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(new_username) > 150:
            return Response(
                {"username": ["Username must be 150 characters or fewer."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(username__iexact=new_username).exclude(pk=user.pk).exists():
            return Response(
                {"username": ["That username is already taken."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_username != user.username:
            user.username = new_username
            user.save(update_fields=["username"])

    avatar_file = request.FILES.get("avatar")
    if avatar_file is not None:
        profile_obj.avatar = avatar_file
        profile_obj.save(update_fields=["avatar"])

    new_phone = request.data.get("phone")
    if new_phone is not None:
        new_phone = str(new_phone).strip()
        if len(new_phone) > 40:
            return Response(
                {"phone": ["Phone number must be 40 characters or fewer."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_phone != profile_obj.phone:
            profile_obj.phone = new_phone
            profile_obj.save(update_fields=["phone"])

    return Response(_me_payload(user, request))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request: Request) -> Response:
    """Let an authenticated user set a new password.

    Requires the current password (the temporary one for first-time sign-ins),
    enforces the platform password policy on the new password, and clears the
    must-reset flag on success.
    """
    user = request.user
    current_password = request.data.get("current_password", "")
    new_password = request.data.get("new_password", "")

    if not current_password or not new_password:
        return Response(
            {"error": "current_password and new_password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not user.check_password(current_password):
        return Response(
            {"current_password": ["Current password is incorrect."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if current_password == new_password:
        return Response(
            {"new_password": ["New password must be different from the current password."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        return Response({"new_password": list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save(update_fields=["password"])
    mark_must_reset_password(user, False)

    return Response({"detail": "Password updated successfully."}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    return Response({"status": "ok"})
