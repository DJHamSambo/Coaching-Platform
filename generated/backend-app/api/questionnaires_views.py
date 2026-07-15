from rest_framework import generics, permissions

from api.models import FoundationalQuestionnaire
from api.questionnaires_serializers import FoundationalQuestionnaireSerializer


class QuestionnairesListView(generics.ListCreateAPIView):
    """List the signed-in user's foundational questionnaires (newest first) and
    create new submissions."""

    serializer_class = FoundationalQuestionnaireSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return FoundationalQuestionnaire.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class QuestionnairesDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = FoundationalQuestionnaireSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return FoundationalQuestionnaire.objects.filter(owner=self.request.user)
