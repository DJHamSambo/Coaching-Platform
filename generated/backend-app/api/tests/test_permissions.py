from datetime import datetime, timezone
from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from api.models import Coachee, Session, UnavailablePeriod, WeeklyAvailabilityWindow
from api.permissions import OwnsObjectPermission


class OwnsObjectPermissionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = OwnsObjectPermission()
        self.owner = User.objects.create_user(username="owner", password="secret")
        self.other = User.objects.create_user(username="other", password="secret")
        self.coachee = Coachee.objects.create(name="A", email="a@example.com", notes="", added_by=self.owner)

    def _request_for(self, user):
        request = self.factory.get("/")
        request.user = user
        return request

    def test_allows_owner_bound_objects(self):
        session = Session.objects.create(title="S", owner=self.owner)
        request = self._request_for(self.owner)

        allowed = self.permission.has_object_permission(request, None, session)

        self.assertTrue(allowed)

    def test_denies_non_owner_for_owner_bound_objects(self):
        session = Session.objects.create(title="S", owner=self.owner)
        request = self._request_for(self.other)

        allowed = self.permission.has_object_permission(request, None, session)

        self.assertFalse(allowed)

    def test_allows_coach_bound_objects(self):
        window = WeeklyAvailabilityWindow.objects.create(
            coach=self.owner,
            weekday=1,
            start_time="09:00",
            end_time="12:00",
        )
        request = self._request_for(self.owner)

        allowed = self.permission.has_object_permission(request, None, window)

        self.assertTrue(allowed)

    def test_denies_when_ownership_fields_missing(self):
        request = self._request_for(self.owner)
        obj = SimpleNamespace(id=1)

        allowed = self.permission.has_object_permission(request, None, obj)

        self.assertFalse(allowed)

    def test_denies_for_anonymous_user(self):
        start_at = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        end_at = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
        period = UnavailablePeriod.objects.create(
            coach=self.owner,
            start_at=start_at,
            end_at=end_at,
            reason="Busy",
        )
        request = self._request_for(AnonymousUser())

        allowed = self.permission.has_object_permission(request, None, period)

        self.assertFalse(allowed)
