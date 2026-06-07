from rest_framework import generics, permissions
from api.users_serializers import UsersSerializer


class UsersListView(generics.ListCreateAPIView):
    serializer_class = UsersSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.serializer_class.Meta.model.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class UsersDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UsersSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.serializer_class.Meta.model.objects.filter(owner=self.request.user)
