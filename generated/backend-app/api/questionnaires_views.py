from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError

from api.models import Coachee, FoundationalQuestionnaire
from api.notifications import notify
from api.questionnaires_serializers import FoundationalQuestionnaireSerializer
from api.relationships import active_coachee_relationships


class QuestionnairesListView(generics.ListCreateAPIView):
    """List the signed-in user's foundational questionnaires (newest first) and
    create new submissions.

    Coaches/admins can instead pass ``?coachee=<id>`` to view the foundational
    questionnaires completed within one of their coaching relationships (or
    any relationship, if admin). Questionnaires completed for a different coach
    are only visible if the coachee shares them (see the shared-data endpoint)."""

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
            return FoundationalQuestionnaire.objects.filter(coachee=coachee).select_related("coachee__added_by")
        return FoundationalQuestionnaire.objects.filter(owner=user).select_related("coachee__added_by")

    def perform_create(self, serializer):
        user = self.request.user
        active = active_coachee_relationships(user)
        coachee = serializer.validated_data.get("coachee")
        if coachee is not None:
            if not active.filter(pk=coachee.pk).exists():
                raise PermissionDenied("You can only complete a questionnaire for a current coach.")
        else:
            # With one current coach there's nothing to choose; with several
            # the coachee must say which coach this questionnaire is for.
            active_list = list(active.select_related("added_by")[:2])
            if len(active_list) > 1:
                raise ValidationError({"coachee": ["Please choose which coach this questionnaire is for."]})
            coachee = active_list[0] if active_list else None

        serializer.save(owner=user, coachee=coachee)
        if coachee is not None:
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
