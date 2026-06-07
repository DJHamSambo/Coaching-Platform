from rest_framework import generics, permissions
from api.resources_serializers import ResourcesSerializer


class ResourcesListView(generics.ListCreateAPIView):
    serializer_class = ResourcesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.serializer_class.Meta.model.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class ResourcesDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ResourcesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.serializer_class.Meta.model.objects.filter(owner=self.request.user)
