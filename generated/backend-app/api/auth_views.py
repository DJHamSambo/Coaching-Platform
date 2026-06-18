from __future__ import annotations

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from api.models import Coachee


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
    return Response({
        "id": user.pk,
        "username": user.username,
        "email": user.email,
        "is_admin": bool(user.is_staff),
        "role": role,
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    return Response({"status": "ok"})
