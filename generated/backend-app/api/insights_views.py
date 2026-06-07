from rest_framework import generics, permissions
from api.insights_serializers import InsightsSerializer


class InsightsListView(generics.ListCreateAPIView):
    serializer_class = InsightsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.serializer_class.Meta.model.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class InsightsDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = InsightsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.serializer_class.Meta.model.objects.filter(owner=self.request.user)
