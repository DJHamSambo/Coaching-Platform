import logging

from rest_framework.permissions import BasePermission


logger = logging.getLogger(__name__)


class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj) -> bool:  # type: ignore[override]
        return getattr(obj, "owner", None) == request.user


class OwnsObjectPermission(BasePermission):
    """Restrict object access to records owned by the authenticated user."""

    message = "You do not have permission to access this resource."

    def has_object_permission(self, request, view, obj) -> bool:  # type: ignore[override]
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        owner_id = getattr(obj, "owner_id", None)
        if owner_id is not None:
            return owner_id == user.id

        coach_id = getattr(obj, "coach_id", None)
        if coach_id is not None:
            return coach_id == user.id

        logger.warning("OwnsObjectPermission: object %s has neither owner_id nor coach_id", obj.__class__.__name__)
        return False
