from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models


class Task(models.Model):
    STATUS_CHOICES = [
        ("backlog", "Backlog"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
    ]
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="backlog")
    assignee = models.CharField(max_length=100, default="Coachee")
    due_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tasks")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Message(models.Model):
    title = models.CharField(max_length=500, help_text="The discussion message text")
    task_id = models.IntegerField(null=True, blank=True)
    author = models.CharField(max_length=100, default="Coach")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="messages")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Session(models.Model):
    MODE_CHOICES = [("video", "Video"), ("in-person", "In Person"), ("phone", "Phone")]
    title = models.CharField(max_length=255)
    date = models.DateTimeField(null=True, blank=True)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="video")
    requested_by = models.CharField(max_length=100, default="coachee")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


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
