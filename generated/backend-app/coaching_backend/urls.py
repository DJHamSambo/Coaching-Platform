from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from api.auth_views import health, me, register
from api.users_views import UsersListView, UsersDetailView
from api.sessions_views import SessionsListView, SessionsDetailView
from api.tasks_views import TasksListView, TasksDetailView
from api.messages_views import MessagesListView, MessagesDetailView
from api.resources_views import ResourcesListView, ResourcesDetailView
from api.insights_views import InsightsListView, InsightsDetailView

urlpatterns = [
    path("health", health, name="health"),
    path("api/auth/register", register, name="auth_register"),
    path("api/auth/login", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/users/me", me, name="users_me"),
    path("api/users/", UsersListView.as_view(), name="users-list"),
    path("api/users/<int:pk>/", UsersDetailView.as_view(), name="users-detail"),
    path("api/sessions/", SessionsListView.as_view(), name="sessions-list"),
    path("api/sessions/<int:pk>/", SessionsDetailView.as_view(), name="sessions-detail"),
    path("api/tasks/", TasksListView.as_view(), name="tasks-list"),
    path("api/tasks/<int:pk>/", TasksDetailView.as_view(), name="tasks-detail"),
    path("api/messages/", MessagesListView.as_view(), name="messages-list"),
    path("api/messages/<int:pk>/", MessagesDetailView.as_view(), name="messages-detail"),
    path("api/resources/", ResourcesListView.as_view(), name="resources-list"),
    path("api/resources/<int:pk>/", ResourcesDetailView.as_view(), name="resources-detail"),
    path("api/insights/", InsightsListView.as_view(), name="insights-list"),
    path("api/insights/<int:pk>/", InsightsDetailView.as_view(), name="insights-detail"),
]
