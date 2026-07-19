from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    """Auth-related metadata that augments the built-in User model."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    must_reset_password = models.BooleanField(
        default=False,
        help_text="True when the user signed in with a temporary password and must set a new one.",
    )
    email_verified = models.BooleanField(
        default=False,
        help_text="True once the user has confirmed their email via an activation link.",
    )
    avatar = models.FileField(
        upload_to="avatars/",
        max_length=255,
        null=True,
        blank=True,
        help_text="Optional profile picture shown in the app header.",
    )
    phone = models.CharField(
        max_length=40,
        blank=True,
        default="",
        help_text="Optional contact phone number shown on the account profile.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Profile<{self.user.username}>"


class EmailVerificationToken(models.Model):
    """A single-use, time-limited token used to activate/verify an account.

    Only the SHA-256 hash of the token is stored; the raw value is emailed to
    the user and never persisted. A token is valid when it has not expired and
    has not already been consumed.
    """

    PURPOSE_ACTIVATION = "activation"
    PURPOSE_CHOICES = [
        (PURPOSE_ACTIVATION, "Account activation"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="verification_tokens"
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    purpose = models.CharField(
        max_length=32, choices=PURPOSE_CHOICES, default=PURPOSE_ACTIVATION
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Token<{self.user.username}:{self.purpose}>"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    def is_valid(self) -> bool:
        return not self.is_used and not self.is_expired



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
    title = models.CharField(max_length=255)
    date = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=60)
    coachee = models.ForeignKey(Coachee, on_delete=models.SET_NULL, null=True, blank=True, related_name="coachee_sessions")
    coaching_plan = models.ForeignKey("CoachingPlan", on_delete=models.SET_NULL, null=True, blank=True, related_name="sessions")
    notes = models.TextField(blank=True, default="")
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="video")
    requested_by = models.CharField(max_length=100, default="coachee")
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
    coachee = models.ForeignKey(Coachee, on_delete=models.SET_NULL, null=True, blank=True, related_name="insights")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Notification(models.Model):
    """An activity notification delivered to a coach or coachee."""
    TYPE_CHOICES = [
        ("mention", "Mention"),
        ("session_booked", "Session Booked"),
        ("task_assigned", "Task Assigned"),
        ("action_created", "Action Created"),
        ("plan_assigned", "Plan Assigned"),
        ("resource_added", "Resource Added"),
        ("contract_awaiting_signature", "Contract Awaiting Signature"),
        ("contract_executed", "Contract Executed"),
    ]
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    actor_name = models.CharField(max_length=150, blank=True, default="", help_text="Display name of who triggered the notification")
    notification_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    message = models.CharField(max_length=500)
    # Navigation context — where clicking the notification should take the user
    target_type = models.CharField(max_length=32, blank=True, default="", help_text="plan | action | session | insight | contract")
    target_id = models.IntegerField(null=True, blank=True)
    plan_id = models.IntegerField(null=True, blank=True)
    action_id = models.IntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "-created_at"])]

    def __str__(self) -> str:
        return f"Notification<{self.notification_type} -> {self.recipient.username}>"


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
    file = models.FileField(upload_to="resources/", max_length=255, null=True, blank=True)
    plan = models.ForeignKey(
        CoachingPlan,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="documents",
        help_text="Optional coaching plan this resource is shared against",
    )
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="resources")
    shared_with = models.ManyToManyField(
        User,
        blank=True,
        related_name="shared_resources",
        help_text="Users this resource has been explicitly shared with",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class FoundationalQuestionnaire(models.Model):
    """A completed foundational questionnaire submitted by a user.

    The questions and answers are stored together as a self-describing list of
    ``{"question": ..., "answer": ...}`` entries so historical submissions stay
    intact even if the question set changes later.
    """

    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="questionnaires"
    )
    name = models.CharField(max_length=255, blank=True, default="")
    answers = models.JSONField(default=list)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self) -> str:
        return f"Questionnaire<{self.owner.username}:{self.submitted_at:%Y-%m-%d}>"


class CoachingContract(models.Model):
    """A saved executive coaching contract created by a coach and assigned to
    a coachee for review, acceptance, and co-signature.

    All of the fillable fields (party details, session terms, signatures) are
    stored together in a self-describing ``data`` JSON object so that saved
    contracts remain intact even if the contract template changes later.
    """

    STATUS_AWAITING_COACHEE = "awaiting_coachee"
    STATUS_EXECUTED = "executed"
    STATUS_CHOICES = [
        (STATUS_AWAITING_COACHEE, "Awaiting coachee signature"),
        (STATUS_EXECUTED, "Fully executed"),
    ]

    coach = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="coach_contracts"
    )
    coachee = models.ForeignKey(
        Coachee, on_delete=models.SET_NULL, null=True, blank=True, related_name="contracts"
    )
    title = models.CharField(max_length=255, blank=True, default="Executive Coaching Contract")
    data = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AWAITING_COACHEE)
    coachee_accepted_terms = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Contract<{self.coach.username}:{self.created_at:%Y-%m-%d}>"
