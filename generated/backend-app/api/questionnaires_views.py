from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied

from api.models import Coachee, FoundationalQuestionnaire
from api.notifications import notify
from api.questionnaires_serializers import FoundationalQuestionnaireSerializer


class QuestionnairesListView(generics.ListCreateAPIView):
    """List the signed-in user's foundational questionnaires (newest first) and
    create new submissions.

    Coaches/admins can instead pass ``?coachee=<id>`` to view the foundational
    questionnaires submitted by a specific coachee they manage (or any coachee,
    if admin)."""

    serializer_class = FoundationalQuestionnaireSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        coachee_id = self.request.query_params.get("coachee")
        if coachee_id:
            try:
                coachee = Coachee.objects.get(pk=coachee_id)
            except (Coachee.DoesNotExist, ValueError):
                return FoundationalQuestionnaire.objects.none()
            if not user.is_staff and coachee.added_by_id != user.id:
                raise PermissionDenied("You do not have permission to view this coachee's questionnaires.")
            if not coachee.user_id:
                return FoundationalQuestionnaire.objects.none()
            return FoundationalQuestionnaire.objects.filter(owner=coachee.user)
        return FoundationalQuestionnaire.objects.filter(owner=user)

    def perform_create(self, serializer):
        questionnaire = serializer.save(owner=self.request.user)
        coachee = Coachee.objects.filter(user=self.request.user).select_related("added_by").first()
        if coachee is not None and coachee.added_by is not None:
            notify(
                coachee.added_by,
                coachee.name,
                "questionnaire_completed",
                f"{coachee.name} completed their foundational questionnaire.",
                target_type="coachee",
                target_id=coachee.id,
            )


class QuestionnairesDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = FoundationalQuestionnaireSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return FoundationalQuestionnaire.objects.filter(owner=self.request.user)
