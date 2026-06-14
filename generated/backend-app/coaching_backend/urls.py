from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from api.users_views import UsersListView, UsersDetailView
from api.tasks_views import TasksListView, TasksDetailView
from api.messages_views import MessagesListView, MessagesDetailView
from api.coachees_views import CoacheesListView, CoacheesDetailView
from api.plans_views import PlansListView, PlansDetailView, PlanActionsListView, PlanActionsDetailView

urlpatterns = [
    path("api/auth/login", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/users/", UsersListView.as_view(), name="users-list"),
    path("api/users/<int:pk>/", UsersDetailView.as_view(), name="users-detail"),
    # Coachees (people managed by coaches)
    path("api/coachees/", CoacheesListView.as_view(), name="coachees-list"),
    path("api/coachees/<int:pk>/", CoacheesDetailView.as_view(), name="coachees-detail"),
    # Coaching plans (sorted by target_date)
    path("api/plans/", PlansListView.as_view(), name="plans-list"),
    path("api/plans/<int:pk>/", PlansDetailView.as_view(), name="plans-detail"),
    # Plan-scoped actions (sequenced)
    path("api/plans/<int:plan_id>/actions/", PlanActionsListView.as_view(), name="plan-actions-list"),
    path("api/plans/<int:plan_id>/actions/<int:pk>/", PlanActionsDetailView.as_view(), name="plan-actions-detail"),
    # Legacy flat task/message endpoints (kept for backwards compatibility)
    path("api/tasks/", TasksListView.as_view(), name="tasks-list"),
    path("api/tasks/<int:pk>/", TasksDetailView.as_view(), name="tasks-detail"),
    path("api/messages/", MessagesListView.as_view(), name="messages-list"),
    path("api/messages/<int:pk>/", MessagesDetailView.as_view(), name="messages-detail"),
]
