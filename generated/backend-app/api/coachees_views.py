from rest_framework import generics, permissions
from django.contrib.auth.models import User
from api.coachees_serializers import CoacheeSerializer
from api.models import Coachee


def _resolve_owner(request) -> User:
    user = request.user
    if user and getattr(user, "is_authenticated", False):
        return user
    owner, _ = User.objects.get_or_create(username="demo_coach", defaults={"email": "demo@example.com"})
    return owner


class CoacheesListView(generics.ListCreateAPIView):
    serializer_class = CoacheeSerializer
    # Creating a coachee can email an invitation to an existing person, so
    # this must never be reachable anonymously (it used to fall back to demo_coach).
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Coachee.objects.filter(added_by=_resolve_owner(self.request)).order_by("name")

    def perform_create(self, serializer):
        serializer.save(added_by=_resolve_owner(self.request))


class CoacheesDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CoacheeSerializer
    # Creating a coachee can email an invitation to an existing person, so
    # this must never be reachable anonymously (it used to fall back to demo_coach).
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Coachee.objects.filter(added_by=_resolve_owner(self.request))
