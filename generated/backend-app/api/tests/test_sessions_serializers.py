from datetime import datetime, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from api.models import UnavailablePeriod, WeeklyAvailabilityWindow
from api.sessions_serializers import UnavailablePeriodSerializer, WeeklyAvailabilityWindowSerializer


class SessionsSerializerValidationTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="coach_a", password="secret")

    def _request(self):
        request = self.factory.post("/")
        request.user = self.user
        return request

    def test_weekly_availability_rejects_overlap(self):
        WeeklyAvailabilityWindow.objects.create(
            coach=self.user,
            weekday=1,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        serializer = WeeklyAvailabilityWindowSerializer(
            data={"weekday": 1, "start_time": "11:00", "end_time": "13:00"},
            context={"request": self._request()},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("overlaps", str(serializer.errors).lower())

    def test_unavailable_period_rejects_overlap(self):
        start = timezone.make_aware(datetime(2026, 6, 1, 9, 0))
        end = timezone.make_aware(datetime(2026, 6, 1, 11, 0))
        UnavailablePeriod.objects.create(coach=self.user, start_at=start, end_at=end, reason="existing")

        serializer = UnavailablePeriodSerializer(
            data={
                "start_at": start + timedelta(hours=1),
                "end_at": end + timedelta(hours=1),
                "reason": "new",
            },
            context={"request": self._request()},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("overlaps", str(serializer.errors).lower())

    def test_weekly_availability_rejects_inverted_range(self):
        serializer = WeeklyAvailabilityWindowSerializer(
            data={"weekday": 2, "start_time": "17:00", "end_time": "09:00"},
            context={"request": self._request()},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("start_time", str(serializer.errors).lower())

    def test_unavailable_period_rejects_inverted_range(self):
        serializer = UnavailablePeriodSerializer(
            data={
                "start_at": timezone.make_aware(datetime(2026, 6, 2, 12, 0)),
                "end_at": timezone.make_aware(datetime(2026, 6, 2, 10, 0)),
                "reason": "invalid",
            },
            context={"request": self._request()},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("start_at", str(serializer.errors).lower())

    def test_overlap_validation_uses_instance_actor_without_request(self):
        first = WeeklyAvailabilityWindow.objects.create(
            coach=self.user,
            weekday=3,
            start_time=time(9, 0),
            end_time=time(11, 0),
        )
        second = WeeklyAvailabilityWindow.objects.create(
            coach=self.user,
            weekday=3,
            start_time=time(12, 0),
            end_time=time(14, 0),
        )

        serializer = WeeklyAvailabilityWindowSerializer(
            instance=second,
            data={"start_time": "10:30", "end_time": "12:30"},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("overlaps", str(serializer.errors).lower())

        first.refresh_from_db()
