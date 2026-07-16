from rest_framework import generics, permissions

from api.models import CoachingContract
from api.contracts_serializers import CoachingContractSerializer


class ContractsListView(generics.ListCreateAPIView):
    """List the signed-in user's coaching contracts (newest first) and create
    new saved contracts."""

    serializer_class = CoachingContractSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CoachingContract.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class ContractsDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = CoachingContractSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CoachingContract.objects.filter(owner=self.request.user)
