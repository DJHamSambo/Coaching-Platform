from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from api.account_provisioning import hash_token, mark_email_verified, mark_must_reset_password
from api.models import EmailVerificationToken


def _lookup_valid_token(raw_token: str) -> EmailVerificationToken | None:
    """Return the matching, still-valid token or ``None``."""
    if not raw_token:
        return None
    try:
        token = EmailVerificationToken.objects.select_related("user").get(
            token_hash=hash_token(raw_token)
        )
    except EmailVerificationToken.DoesNotExist:
        return None
    return token if token.is_valid() else None


@api_view(["POST"])
@permission_classes([AllowAny])
def validate_activation_token(request: Request) -> Response:
    """Check an activation token so the SPA can render the set-password form.

    Returns the associated username/email on success so the UI can greet the
    user; reveals nothing when the token is missing, expired, or already used.
    """
    raw_token = str(request.data.get("token", "")).strip()
    token = _lookup_valid_token(raw_token)
    if token is None:
        return Response(
            {"valid": False, "detail": "This link is invalid or has expired."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {"valid": True, "username": token.user.username, "email": token.user.email},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def activate_account(request: Request) -> Response:
    """Consume an activation token: verify the email and set the user's password.

    On success the account is activated, the email is marked verified, the
    must-reset flag is cleared, and the single-use token is consumed.
    """
    raw_token = str(request.data.get("token", "")).strip()
    new_password = request.data.get("new_password", "")

    if not raw_token or not new_password:
        return Response(
            {"detail": "token and new_password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        try:
            token = (
                EmailVerificationToken.objects.select_for_update()
                .select_related("user")
                .get(token_hash=hash_token(raw_token))
            )
        except EmailVerificationToken.DoesNotExist:
            return Response(
                {"detail": "This link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not token.is_valid():
            return Response(
                {"detail": "This link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = token.user
        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as exc:
            return Response({"new_password": list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.is_active = True
        user.save(update_fields=["password", "is_active"])

        token.used_at = timezone.now()
        token.save(update_fields=["used_at"])

        mark_email_verified(user, True)
        mark_must_reset_password(user, False)

    return Response(
        {"detail": "Your account is activated. You can now sign in.", "username": user.username},
        status=status.HTTP_200_OK,
    )
