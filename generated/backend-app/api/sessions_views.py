from rest_framework import generics, permissions
from api.sessions_serializers import SessionsSerializer


class SessionsListView(generics.ListCreateAPIView):
    serializer_class = SessionsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.serializer_class.Meta.model.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class SessionsDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SessionsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.serializer_class.Meta.model.objects.filter(owner=self.request.user)
