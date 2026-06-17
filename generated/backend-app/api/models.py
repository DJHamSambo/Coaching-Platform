from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models


class Coachee(models.Model):
    """A coachee managed by coaches within the platform."""
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="coachee_profiles")
    added_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="coachees")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class CoachingPlan(models.Model):
    """A coaching plan owned by a coach and assigned to a coachee."""
    STATUS_CHOICES = [
        ("todo", "To Do"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
    ]
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    goal = models.TextField(blank=True, default="", help_text="Overall coaching goal for this plan")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="todo")
    target_date = models.DateField(null=True, blank=True)
    coachee = models.ForeignKey(Coachee, on_delete=models.SET_NULL, null=True, blank=True, related_name="plans")
    coach = models.ForeignKey(User, on_delete=models.CASCADE, related_name="coaching_plans")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["target_date"]

    def __str__(self) -> str:
        return self.title


class Task(models.Model):
    """An action item within a coaching plan."""
    STATUS_CHOICES = [
        ("backlog", "Backlog"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
    ]
    plan = models.ForeignKey(CoachingPlan, on_delete=models.CASCADE, related_name="actions", null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="backlog")
    assignee = models.CharField(max_length=100, default="Coachee")
    order = models.PositiveIntegerField(default=0, help_text="Sequence position within the plan")
    due_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tasks")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self) -> str:
        return self.title


class Message(models.Model):
    """A discussion message on an action or coaching plan."""
    title = models.CharField(max_length=500, help_text="The discussion message text")
    plan = models.ForeignKey(CoachingPlan, on_delete=models.CASCADE, related_name="messages", null=True, blank=True)
    task_id = models.IntegerField(null=True, blank=True)
    author = models.CharField(max_length=100, default="Coach")
    mentions = models.CharField(max_length=500, blank=True, default="", help_text="Comma-separated @mention names")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="messages")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Session(models.Model):
    MODE_CHOICES = [("video", "Video"), ("in-person", "In Person"), ("phone", "Phone")]
    STATUS_CHOICES = [
        ("requested", "Requested"),
        ("accepted", "Accepted"),
        ("proposed", "Proposed new time"),
        ("rejected", "Rejected"),
    ]
    title = models.CharField(max_length=255)
    date = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=60)
    coachee = models.ForeignKey(Coachee, on_delete=models.SET_NULL, null=True, blank=True, related_name="coachee_sessions")
    notes = models.TextField(blank=True, default="")
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="video")
    requested_by = models.CharField(max_length=100, default="coachee")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="accepted")
    response_note = models.TextField(blank=True, default="")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class WeeklyAvailabilityWindow(models.Model):
    WEEKDAY_CHOICES = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    coach = models.ForeignKey(User, on_delete=models.CASCADE, related_name="weekly_availability_windows")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["weekday", "start_time"]
        indexes = [models.Index(fields=["coach", "weekday", "start_time"])]


class UnavailablePeriod(models.Model):
    coach = models.ForeignKey(User, on_delete=models.CASCADE, related_name="unavailable_periods")
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    reason = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_at"]
        indexes = [models.Index(fields=["coach", "start_at", "end_at"])]


class Insight(models.Model):
    title = models.CharField(max_length=1000, help_text="The insight/journal note text")
    author = models.CharField(max_length=100, default="Coach")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="insights")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Resource(models.Model):
    CATEGORY_CHOICES = [
        ("guide", "Guide"),
        ("tool", "Tool"),
        ("template", "Template"),
        ("article", "Article"),
    ]
    SCOPE_CHOICES = [("shared", "Shared"), ("private", "Private")]
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default="guide")
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="shared")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="resources")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
