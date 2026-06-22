from rest_framework import generics, permissions
from django.db.models import Q
from api.insights_serializers import InsightsSerializer
from api.models import Coachee


class InsightsListView(generics.ListCreateAPIView):
    serializer_class = InsightsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Check if user is a coachee
        is_coachee = Coachee.objects.filter(user=user).exists()
        
        if is_coachee:
            # Coachees see:
            # 1. Insights created by their coaches (assigned to them)
            # 2. Insights they created themselves
            coachee = Coachee.objects.get(user=user)
            return self.serializer_class.Meta.model.objects.filter(
                Q(coachee=coachee) | Q(owner=user)
            ).order_by('-created_at')
        else:
            # Coaches see insights they created (including those assigned to their coachees)
            return self.serializer_class.Meta.model.objects.filter(owner=user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class InsightsDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = InsightsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Check if user is a coachee
        is_coachee = Coachee.objects.filter(user=user).exists()
        
        if is_coachee:
            # Coachees can only access insights assigned to them or created by them
            coachee = Coachee.objects.get(user=user)
            return self.serializer_class.Meta.model.objects.filter(
                Q(coachee=coachee) | Q(owner=user)
            )
        else:
            # Coaches can only access their own insights
            return self.serializer_class.Meta.model.objects.filter(owner=user)
