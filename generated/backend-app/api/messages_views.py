from rest_framework import generics, permissions
from api.messages_serializers import MessagesSerializer


class MessagesListView(generics.ListCreateAPIView):
    serializer_class = MessagesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.serializer_class.Meta.model.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class MessagesDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MessagesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.serializer_class.Meta.model.objects.filter(owner=self.request.user)
