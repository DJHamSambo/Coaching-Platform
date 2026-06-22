from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
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
            # Coaches see:
            # 1. All insights from their coachees (regardless of who created them)
            # 2. Insights they created themselves
            coach_coachees = Coachee.objects.filter(added_by=user)
            queryset = self.serializer_class.Meta.model.objects.filter(
                Q(coachee__in=coach_coachees) | Q(owner=user)
            ).order_by('-created_at')
            
            # Support filtering by coachee_id
            coachee_id = self.request.query_params.get('coachee_id')
            if coachee_id:
                queryset = queryset.filter(coachee_id=coachee_id)
            
            return queryset

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
            # Coaches can access all insights related to their coachees plus their own
            coach_coachees = Coachee.objects.filter(added_by=user)
            return self.serializer_class.Meta.model.objects.filter(
                Q(coachee__in=coach_coachees) | Q(owner=user)
            )

    def perform_update(self, serializer):
        # Only allow users to edit insights they created
        if serializer.instance.owner != self.request.user:
            raise PermissionDenied("You can only edit insights you created.")
        serializer.save()

    def perform_destroy(self, instance):
        # Only allow users to delete insights they created
        if instance.owner != self.request.user:
            raise PermissionDenied("You can only delete insights you created.")
        instance.delete()
