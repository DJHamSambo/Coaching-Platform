from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from api.auth_views import register, me, health, change_password
from api.resources_views import ResourcesListView, ResourcesDetailView
from api.administration_views import CoachesListView, CoachesDetailView, AdminCoacheesListView, AdminCoacheesDetailView, CoachDirectoryListView
from api.users_views import UsersListView, UsersDetailView
from api.tasks_views import TasksListView, TasksDetailView
from api.messages_views import MessagesListView, MessagesDetailView
from api.coachees_views import CoacheesListView, CoacheesDetailView
from api.plans_views import PlansListView, PlansDetailView, PlanActionsListView, PlanActionsDetailView
from api.insights_views import InsightsListView, InsightsDetailView
from api.notifications_views import NotificationsListView, NotificationsDetailView, mark_all_read
from api.sessions_views import (
    MyCalendarCoachesListView,
    SessionsListView,
    SessionsDetailView,
    WeeklyAvailabilityWindowListView,
    WeeklyAvailabilityWindowDetailView,
    UnavailablePeriodListView,
    UnavailablePeriodDetailView,
)

urlpatterns = [
    path("api/auth/register/", register, name="register"),
    path("api/auth/me/", me, name="me"),
    path("api/auth/change-password/", change_password, name="change-password"),
    path("api/auth/health/", health, name="health"),
    path("api/auth/login", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair_slash"),
    path("api/auth/refresh", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh_slash"),
    path("api/admin/coaches/", CoachesListView.as_view(), name="admin-coaches-list"),
    path("api/admin/coaches/<int:pk>/", CoachesDetailView.as_view(), name="admin-coaches-detail"),
    path("api/admin/coach-directory/", CoachDirectoryListView.as_view(), name="admin-coach-directory-list"),
    path("api/admin/coachees/", AdminCoacheesListView.as_view(), name="admin-coachees-list"),
    path("api/admin/coachees/<int:pk>/", AdminCoacheesDetailView.as_view(), name="admin-coachees-detail"),
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
    # Calendar sessions and coach availability
    path("api/calendar/my-coaches/", MyCalendarCoachesListView.as_view(), name="calendar-my-coaches-list"),
    path("api/sessions/", SessionsListView.as_view(), name="sessions-list"),
    path("api/sessions/<int:pk>/", SessionsDetailView.as_view(), name="sessions-detail"),
    path("api/availability/windows/", WeeklyAvailabilityWindowListView.as_view(), name="availability-windows-list"),
    path("api/availability/windows/<int:pk>/", WeeklyAvailabilityWindowDetailView.as_view(), name="availability-windows-detail"),
    path("api/availability/unavailable/", UnavailablePeriodListView.as_view(), name="unavailable-periods-list"),
    path("api/availability/unavailable/<int:pk>/", UnavailablePeriodDetailView.as_view(), name="unavailable-periods-detail"),
    # Legacy flat task/message endpoints (kept for backwards compatibility)
    path("api/tasks/", TasksListView.as_view(), name="tasks-list"),
    path("api/tasks/<int:pk>/", TasksDetailView.as_view(), name="tasks-detail"),
    path("api/messages/", MessagesListView.as_view(), name="messages-list"),
    path("api/messages/<int:pk>/", MessagesDetailView.as_view(), name="messages-detail"),
    path("api/insights/", InsightsListView.as_view(), name="insights-list"),
    path("api/insights/<int:pk>/", InsightsDetailView.as_view(), name="insights-detail"),
    # Activity notifications
    path("api/notifications/", NotificationsListView.as_view(), name="notifications-list"),
    path("api/notifications/mark-all-read/", mark_all_read, name="notifications-mark-all-read"),
    path("api/notifications/<int:pk>/", NotificationsDetailView.as_view(), name="notifications-detail"),
    # Shared coaching resources / documents (optionally linked to a plan)
    path("api/resources/", ResourcesListView.as_view(), name="resources-list"),
    path("api/resources/<int:pk>/", ResourcesDetailView.as_view(), name="resources-detail"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
