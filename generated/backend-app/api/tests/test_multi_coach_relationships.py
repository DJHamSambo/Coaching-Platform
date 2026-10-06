"""A coachee is one person (one login) with one relationship per coach.

Data created within a relationship stays between that coach and coachee; a new
coach only gains access after the coachee accepts, and only sees data from
another relationship when the coachee explicitly shares it.
"""

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from api.account_provisioning import create_activation_token
from api.models import (
    Coachee,
    CoachingPlan,
    DataShare,
    FoundationalQuestionnaire,
    Insight,
    Notification,
)

ANSWERS = [{"question": "What do you want?", "answer": "Growth"}]


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    ACCOUNT_ACTIVATION_URL="https://example.test/",
    FRONTEND_LOGIN_URL="https://example.test/",
)
class MultiCoachRelationshipTests(TestCase):
    def setUp(self):
        self.coach_a = User.objects.create_user(username="coach_a", password="x", email="a@coach.test")
        self.coach_b = User.objects.create_user(username="coach_b", password="x", email="b@coach.test")

        # Coach A adds Jo, who activates their new account.
        response = self._client(self.coach_a).post(
            "/api/admin/coachees/", {"name": "Jo Bloggs", "email": "jo@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.rel_a = Coachee.objects.get(pk=response.data["id"])
        self.jo = self.rel_a.user
        self._activate(self.jo)
        self.rel_a.refresh_from_db()
        mail.outbox.clear()

    # -- helpers -----------------------------------------------------------

    def _client(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def _activate(self, user):
        raw = create_activation_token(user)
        response = APIClient().post(
            "/api/auth/activate/", {"token": raw, "new_password": "Str0ng!Passw0rd"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        user.refresh_from_db()

    def _coach_b_adds_jo(self, email="JO@example.com"):
        return self._client(self.coach_b).post(
            "/api/admin/coachees/", {"name": "Jo", "email": email}, format="json"
        )

    def _accept(self, rel):
        return self._client(self.jo).post(f"/api/relationships/{rel.id}/accept/")

    # -- identity & consent -------------------------------------------------

    def test_activation_accepts_the_inviting_coach(self):
        self.assertEqual(self.rel_a.status, Coachee.STATUS_ACTIVE)
        self.assertTrue(self.jo.is_active)

    def test_second_coach_reuses_the_same_login_and_invites(self):
        users_before = User.objects.count()
        response = self._coach_b_adds_jo()

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(User.objects.count(), users_before)
        rel_b = Coachee.objects.get(pk=response.data["id"])
        self.assertEqual(rel_b.user, self.jo)
        self.assertEqual(rel_b.status, Coachee.STATUS_INVITED)
        self.assertIs(response.data["invitation_sent"], True)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("would like to coach you", mail.outbox[0].subject)
        self.assertTrue(
            Notification.objects.filter(recipient=self.jo, notification_type="coaching_invitation").exists()
        )

    def test_new_and_existing_coachees_look_the_same_to_the_coach(self):
        existing = self._coach_b_adds_jo().data
        new = self._client(self.coach_b).post(
            "/api/admin/coachees/", {"name": "Sam", "email": "sam@example.com"}, format="json"
        ).data
        for field in ("status", "invitation_sent"):
            self.assertEqual(existing[field], new[field])

    def test_coach_cannot_add_a_coach_account_as_a_coachee(self):
        response = self._client(self.coach_b).post(
            "/api/admin/coachees/", {"name": "A", "email": "a@coach.test"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_same_coach_cannot_add_the_same_person_twice(self):
        response = self._client(self.coach_a).post(
            "/api/admin/coachees/", {"name": "Jo again", "email": "jo@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_coach_cannot_write_the_user_link(self):
        response = self._client(self.coach_b).post(
            "/api/admin/coachees/", {"name": "Hijack", "user": self.jo.id}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(Coachee.objects.get(pk=response.data["id"]).user)

    def test_accept_and_decline(self):
        rel_b = Coachee.objects.get(pk=self._coach_b_adds_jo().data["id"])
        self.assertEqual(self._accept(rel_b).status_code, 200)
        rel_b.refresh_from_db()
        self.assertEqual(rel_b.status, Coachee.STATUS_ACTIVE)
        self.assertTrue(
            Notification.objects.filter(recipient=self.coach_b, notification_type="invitation_accepted").exists()
        )
        # Can't accept twice.
        self.assertEqual(self._accept(rel_b).status_code, 400)

    def test_declined_invitation_can_be_reissued(self):
        rel_b = Coachee.objects.get(pk=self._coach_b_adds_jo().data["id"])
        self._client(self.jo).post(f"/api/relationships/{rel_b.id}/decline/")
        rel_b.refresh_from_db()
        self.assertEqual(rel_b.status, Coachee.STATUS_DECLINED)

        response = self._coach_b_adds_jo()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["id"], rel_b.id)
        rel_b.refresh_from_db()
        self.assertEqual(rel_b.status, Coachee.STATUS_INVITED)

    def test_other_users_cannot_respond_to_an_invitation(self):
        rel_b = Coachee.objects.get(pk=self._coach_b_adds_jo().data["id"])
        response = self._client(self.coach_a).post(f"/api/relationships/{rel_b.id}/accept/")
        self.assertEqual(response.status_code, 403)

    def test_either_party_can_end_a_relationship(self):
        response = self._client(self.coach_a).post(f"/api/relationships/{self.rel_a.id}/end/")
        self.assertEqual(response.status_code, 200, response.data)
        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.status, Coachee.STATUS_ENDED)

    # -- privacy between relationships -------------------------------------

    def test_coachee_cannot_see_a_pending_coachs_plan_until_accepting(self):
        rel_b = Coachee.objects.get(pk=self._coach_b_adds_jo().data["id"])
        plan = CoachingPlan.objects.create(title="B plan", coach=self.coach_b, coachee=rel_b)

        ids = [p["id"] for p in self._client(self.jo).get("/api/plans/").data]
        self.assertNotIn(plan.id, ids)

        self._accept(rel_b)
        ids = [p["id"] for p in self._client(self.jo).get("/api/plans/").data]
        self.assertIn(plan.id, ids)

    def test_pending_relationship_gets_no_plan_notifications(self):
        rel_b = Coachee.objects.get(pk=self._coach_b_adds_jo().data["id"])
        self._client(self.coach_b).post(
            "/api/plans/", {"title": "Prep", "coachee": rel_b.id}, format="json"
        )
        self.assertFalse(
            Notification.objects.filter(recipient=self.jo, notification_type="plan_assigned").exists()
        )

    def test_coach_cannot_attach_a_plan_to_another_coachs_coachee(self):
        response = self._client(self.coach_b).post(
            "/api/plans/", {"title": "Sneaky", "coachee": self.rel_a.id}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_insights_stay_within_their_relationship(self):
        rel_b = Coachee.objects.get(pk=self._coach_b_adds_jo().data["id"])
        self._accept(rel_b)
        a_note = Insight.objects.create(title="A's note", owner=self.coach_a, coachee=self.rel_a)

        # Coachee with two relationships can list insights (used to crash).
        response = self._client(self.jo).get("/api/insights/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(a_note.id, [i["id"] for i in response.data])

        b_ids = [i["id"] for i in self._client(self.coach_b).get("/api/insights/").data]
        self.assertNotIn(a_note.id, b_ids)

        # Coach B can't file an insight under coach A's relationship.
        response = self._client(self.coach_b).post(
            "/api/insights/", {"title": "x", "coachee": self.rel_a.id}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_questionnaires_are_tagged_to_a_coach_and_not_visible_to_others(self):
        q = self._client(self.jo).post(
            "/api/questionnaires/", {"name": "Q1", "answers": ANSWERS}, format="json"
        )
        self.assertEqual(q.status_code, 201, q.data)
        self.assertEqual(q.data["coachee"], self.rel_a.id)

        rel_b = Coachee.objects.get(pk=self._coach_b_adds_jo().data["id"])
        self._accept(rel_b)
        b_view = self._client(self.coach_b).get(f"/api/questionnaires/?coachee={rel_b.id}")
        self.assertEqual(b_view.data, [])
        a_view = self._client(self.coach_a).get(f"/api/questionnaires/?coachee={self.rel_a.id}")
        self.assertEqual([x["id"] for x in a_view.data], [q.data["id"]])

    def test_questionnaire_needs_a_coach_when_there_are_several(self):
        rel_b = Coachee.objects.get(pk=self._coach_b_adds_jo().data["id"])
        self._accept(rel_b)
        client = self._client(self.jo)

        response = client.post("/api/questionnaires/", {"answers": ANSWERS}, format="json")
        self.assertEqual(response.status_code, 400)

        Notification.objects.all().delete()
        response = client.post(
            "/api/questionnaires/", {"answers": ANSWERS, "coachee": rel_b.id}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        notified = Notification.objects.filter(notification_type="questionnaire_completed")
        self.assertEqual([n.recipient for n in notified], [self.coach_b])

    # -- sharing ------------------------------------------------------------

    def test_sharing_is_opt_in_read_only_and_revocable(self):
        plan = CoachingPlan.objects.create(title="A plan", coach=self.coach_a, coachee=self.rel_a)
        rel_b = Coachee.objects.get(pk=self._coach_b_adds_jo().data["id"])
        self._accept(rel_b)
        coach_b = self._client(self.coach_b)
        jo = self._client(self.jo)

        # Nothing shared by default.
        self.assertEqual(coach_b.get(f"/api/coachees/{rel_b.id}/shared/").data["plans"], [])
        self.assertNotIn(plan.id, [p["id"] for p in coach_b.get("/api/plans/").data])

        shareable = jo.get(f"/api/relationships/{rel_b.id}/shareable/").data
        self.assertEqual([p["id"] for p in shareable["plans"]], [plan.id])
        self.assertIsNone(shareable["plans"][0]["share_id"])

        share = jo.post(
            f"/api/relationships/{rel_b.id}/shares/", {"item_type": "plan", "item_id": plan.id}, format="json"
        )
        self.assertEqual(share.status_code, 201, share.data)
        shared = coach_b.get(f"/api/coachees/{rel_b.id}/shared/").data
        self.assertEqual([p["id"] for p in shared["plans"]], [plan.id])
        self.assertNotIn("coach_username", shared["plans"][0])

        # Shared plans stay out of coach B's own (editable) plan endpoints.
        self.assertEqual(coach_b.get(f"/api/plans/{plan.id}/").status_code, 404)

        # Sharing twice is idempotent.
        again = jo.post(
            f"/api/relationships/{rel_b.id}/shares/", {"item_type": "plan", "item_id": plan.id}, format="json"
        )
        self.assertEqual(again.status_code, 200)

        revoke = jo.delete(f"/api/relationships/{rel_b.id}/shares/{share.data['id']}/")
        self.assertEqual(revoke.status_code, 204)
        self.assertEqual(coach_b.get(f"/api/coachees/{rel_b.id}/shared/").data["plans"], [])
        self.assertTrue(DataShare.objects.filter(pk=share.data["id"], revoked_at__isnull=False).exists())

    def test_cannot_share_with_a_pending_coach(self):
        plan = CoachingPlan.objects.create(title="A plan", coach=self.coach_a, coachee=self.rel_a)
        rel_b = Coachee.objects.get(pk=self._coach_b_adds_jo().data["id"])
        response = self._client(self.jo).post(
            f"/api/relationships/{rel_b.id}/shares/", {"item_type": "plan", "item_id": plan.id}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_cannot_share_someone_elses_item(self):
        other = User.objects.create_user(username="other", password="x")
        other_rel = Coachee.objects.create(name="Other", added_by=self.coach_a, user=other)
        their_q = FoundationalQuestionnaire.objects.create(owner=other, coachee=other_rel, answers=ANSWERS)
        rel_b = Coachee.objects.get(pk=self._coach_b_adds_jo().data["id"])
        self._accept(rel_b)
        response = self._client(self.jo).post(
            f"/api/relationships/{rel_b.id}/shares/",
            {"item_type": "questionnaire", "item_id": their_q.id},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_only_the_relationships_coach_can_read_shared_data(self):
        rel_b = Coachee.objects.get(pk=self._coach_b_adds_jo().data["id"])
        self._accept(rel_b)
        response = self._client(self.coach_a).get(f"/api/coachees/{rel_b.id}/shared/")
        self.assertEqual(response.status_code, 403)
