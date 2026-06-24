from __future__ import annotations

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from api.account_provisioning import mark_must_reset_password
from api.models import Coachee, UserProfile


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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request: Request) -> Response:
    user = request.user
    # Prefer FK link; only fall back to name for legacy coachees with no linked user account
    has_coachee_profile = (
        Coachee.objects.filter(user=user).exists()
        or Coachee.objects.filter(user__isnull=True, name__iexact=user.username).exists()
    )

    role = "admin" if user.is_staff else ("coachee" if has_coachee_profile else "coach")
    must_reset = UserProfile.objects.filter(user=user, must_reset_password=True).exists()
    return Response({
        "id": user.pk,
        "username": user.username,
        "email": user.email,
        "is_admin": bool(user.is_staff),
        "role": role,
        "must_reset_password": must_reset,
    })


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
