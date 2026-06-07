from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj) -> bool:  # type: ignore[override]
        return getattr(obj, "owner", None) == request.user
