"""Covers the coachee invitation path.

These emails were silently dropped in Azure for the whole life of the deployed
app: with no RESEND_API_KEY app setting Django fell back to the console backend,
which reports every send as successful. The tests below pin down the two things
that made that invisible - that a message is actually produced, and that a
backend which sends nothing is reported as a failure rather than a success.
"""

from django.contrib.auth.models import User
from django.core import mail
from django.core.mail.backends.base import BaseEmailBackend
from django.test import TestCase, override_settings

from api.account_provisioning import provision_coachee_login
from api.administration_serializers import AdminCoacheeSerializer
from api.models import Coachee


class SilentEmailBackend(BaseEmailBackend):
    """Accepts messages and delivers none, without raising.

    Mirrors ResendEmailBackend when RESEND_API_KEY is missing or the `resend`
    package is absent: send_messages() returns 0 rather than throwing. Django's
    own dummy backend is no use here - it reports the full message count.
    """

    def send_messages(self, email_messages):
        return 0


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="Coaching Platform <noreply@successby1000cuts.com>",
    ACCOUNT_ACTIVATION_URL="https://example.azurestaticapps.net/",
)
class ProvisionCoacheeLoginTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="secret")

    def _coachee(self, **overrides):
        fields = {
            "name": "Greg Smith",
            "email": "greg@example.com",
            "notes": "",
            "added_by": self.admin,
        }
        fields.update(overrides)
        return Coachee.objects.create(**fields)

    def test_sends_one_activation_email_with_an_absolute_link(self):
        coachee = self._coachee()

        user = provision_coachee_login(coachee)

        self.assertIsNotNone(user)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["greg@example.com"])
        self.assertEqual(message.from_email, "Coaching Platform <noreply@successby1000cuts.com>")
        # The link must be absolute and carry the token, or the invitation is
        # unusable - the old localhost default produced exactly that.
        self.assertIn("https://example.azurestaticapps.net/?token=", message.body)
        self.assertTrue(coachee.invitation_sent)

    def test_account_is_created_inactive_pending_activation(self):
        user = provision_coachee_login(self._coachee())

        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())

    def test_no_email_address_provisions_nothing(self):
        coachee = self._coachee(email="")

        self.assertIsNone(provision_coachee_login(coachee))
        self.assertEqual(len(mail.outbox), 0)
        # None, not False: no invitation was due, so there is nothing to warn about.
        self.assertIsNone(coachee.invitation_sent)

    def test_questionnaire_request_is_carried_into_the_link(self):
        coachee = self._coachee()

        provision_coachee_login(coachee, request_questionnaire=True)

        self.assertIn("next=questionnaire", mail.outbox[0].body)

    def test_serializer_reports_the_invitation_result(self):
        serializer = AdminCoacheeSerializer(
            data={"name": "Greg Smith", "email": "greg@example.com", "notes": ""}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save(added_by=self.admin)

        self.assertIs(serializer.data["invitation_sent"], True)


class SilentBackendTests(TestCase):
    """A backend that accepts nothing must not be reported as success."""

    @override_settings(
        EMAIL_BACKEND="api.tests.test_account_provisioning.SilentEmailBackend"
    )
    def test_backend_that_sends_nothing_is_reported_as_failure(self):
        admin = User.objects.create_user(username="admin2", password="secret")
        coachee = Coachee.objects.create(
            name="Greg Smith", email="greg@example.com", notes="", added_by=admin
        )

        provision_coachee_login(coachee)

        self.assertIs(coachee.invitation_sent, False)
