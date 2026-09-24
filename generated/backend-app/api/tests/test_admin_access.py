"""Regression tests for two admin-facing bugs found in the deployed app.

1. Creating a coach from the UI always failed: the form has no password field
   and posted an empty string, which the serializer rejected as blank.
2. Admins could not open or edit a coaching plan created by another coach,
   because the plan queries filtered on coach=<the requesting user>.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from api.models import Coachee, CoachingPlan, Task


class CreateCoachTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="secret", is_staff=True
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_blank_password_provisions_an_activation_account(self):
        """The Add coach form posts password='' - that must not be rejected."""
        response = self.client.post(
            "/api/admin/coaches/",
            {
                "username": "CoachHam",
                "email": "harmstrong@ct.com.au",
                "password": "",
                "is_staff": False,
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        created = User.objects.get(username="CoachHam")
        # No password is transmitted; the coach activates via the emailed link.
        self.assertFalse(created.has_usable_password())
        self.assertFalse(created.is_active)

    def test_omitted_password_also_works(self):
        response = self.client.post(
            "/api/admin/coaches/",
            {"username": "CoachTwo", "email": "two@example.com", "is_staff": False},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)

    def test_explicit_password_is_honoured(self):
        response = self.client.post(
            "/api/admin/coaches/",
            {
                "username": "CoachThree",
                "email": "three@example.com",
                "password": "Str0ng!Passw0rd",
                "is_staff": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        created = User.objects.get(username="CoachThree")
        self.assertTrue(created.check_password("Str0ng!Passw0rd"))


class AdminPlanAccessTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="secret", is_staff=True
        )
        self.coach = User.objects.create_user(username="coach", password="secret")
        self.coachee = Coachee.objects.create(
            name="Greg Smith", email="greg@example.com", notes="", added_by=self.coach
        )
        # A plan owned by someone other than the admin.
        self.plan = CoachingPlan.objects.create(
            title="Original title", coach=self.coach, coachee=self.coachee
        )
        self.client = APIClient()

    def test_admin_can_see_another_coachs_plan(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get(f"/api/plans/{self.plan.id}/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["title"], "Original title")

    def test_admin_can_edit_another_coachs_plan(self):
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f"/api/plans/{self.plan.id}/", {"title": "Edited by admin"}, format="json"
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.title, "Edited by admin")

    def test_admin_sees_every_plan_in_the_list(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get("/api/plans/")

        self.assertEqual(response.status_code, 200)
        titles = [p["title"] for p in response.data]
        self.assertIn("Original title", titles)

    def test_admin_can_read_actions_on_another_coachs_plan(self):
        Task.objects.create(plan=self.plan, title="Do the thing", owner=self.coach)
        self.client.force_authenticate(self.admin)

        response = self.client.get(f"/api/plans/{self.plan.id}/actions/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data), 1)

    def test_owning_coach_can_still_edit_their_own_plan(self):
        """The admin branch must not regress the ordinary coach path."""
        self.client.force_authenticate(self.coach)

        response = self.client.patch(
            f"/api/plans/{self.plan.id}/", {"title": "Edited by coach"}, format="json"
        )

        self.assertEqual(response.status_code, 200, response.data)

    def test_unrelated_coach_still_cannot_edit_the_plan(self):
        """Widening access for admins must not widen it for everyone."""
        other = User.objects.create_user(username="other_coach", password="secret")
        self.client.force_authenticate(other)

        response = self.client.patch(
            f"/api/plans/{self.plan.id}/", {"title": "Should not work"}, format="json"
        )

        self.assertEqual(response.status_code, 404)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.title, "Original title")
