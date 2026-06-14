from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from api.users_views import UsersListView, UsersDetailView
from api.tasks_views import TasksListView, TasksDetailView
from api.messages_views import MessagesListView, MessagesDetailView

urlpatterns = [
    path("api/auth/login", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/users/", UsersListView.as_view(), name="users-list"),
    path("api/users/<int:pk>/", UsersDetailView.as_view(), name="users-detail"),
    path("api/tasks/", TasksListView.as_view(), name="tasks-list"),
    path("api/tasks/<int:pk>/", TasksDetailView.as_view(), name="tasks-detail"),
    path("api/messages/", MessagesListView.as_view(), name="messages-list"),
    path("api/messages/<int:pk>/", MessagesDetailView.as_view(), name="messages-detail"),
]
