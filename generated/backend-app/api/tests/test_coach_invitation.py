"""Coach onboarding must mirror coachee onboarding, minus the questionnaire.

A coach created without a password gets the same activation email: verify the
address, choose a password, no password ever transmitted. The only difference
is that coaches are never asked to complete a foundational questionnaire.
"""

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from api.models import EmailVerificationToken


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="Coaching Platform <noreply@successby1000cuts.com>",
    ACCOUNT_ACTIVATION_URL="https://example.azurestaticapps.net/",
)
class CoachInvitationEmailTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="secret", is_staff=True
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def _create_coach(self, **overrides):
        payload = {
            "username": "CoachHam",
            "email": "harmstrong@ct.com.au",
            "password": "",
            "is_staff": False,
            "is_active": True,
        }
        payload.update(overrides)
        return self.client.post("/api/admin/coaches/", payload, format="json")

    def test_creating_a_coach_sends_one_activation_email(self):
        response = self._create_coach()

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["harmstrong@ct.com.au"])
        self.assertEqual(
            message.from_email, "Coaching Platform <noreply@successby1000cuts.com>"
        )
        self.assertIn("Activate your Coaching Platform account", message.subject)

    def test_email_addresses_them_as_a_coach_with_a_working_link(self):
        self._create_coach()

        body = mail.outbox[0].body
        self.assertIn("as a coach", body)
        self.assertIn("https://example.azurestaticapps.net/?token=", body)

    def test_coaches_are_not_asked_for_the_questionnaire(self):
        self._create_coach()

        body = mail.outbox[0].body
        self.assertNotIn("questionnaire", body.lower())
        # The coachee email appends ?next=questionnaire; a coach's must not.
        self.assertNotIn("next=questionnaire", body)

    def test_account_is_inactive_until_the_link_is_redeemed(self):
        self._create_coach()

        coach = User.objects.get(username="CoachHam")
        self.assertFalse(coach.is_active)
        self.assertFalse(coach.has_usable_password())
        self.assertTrue(
            EmailVerificationToken.objects.filter(user=coach, used_at__isnull=True).exists()
        )

    def test_supplying_a_password_skips_the_invitation(self):
        """An explicitly set password means the coach can sign in directly."""
        response = self._create_coach(password="Str0ng!Passw0rd")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(mail.outbox), 0)

    def test_response_reports_whether_the_invitation_was_sent(self):
        """Parity with coachees: a failed invitation must not look like success."""
        response = self._create_coach()

        self.assertIs(response.data.get("invitation_sent"), True)
