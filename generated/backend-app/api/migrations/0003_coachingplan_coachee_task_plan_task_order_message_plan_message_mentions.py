from __future__ import annotations

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0002_message_task_id"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Coachee table
        migrations.CreateModel(
            name="Coachee",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("email", models.EmailField(blank=True, default="")),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "added_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="coachees",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        # CoachingPlan table
        migrations.CreateModel(
            name="CoachingPlan",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("goal", models.TextField(blank=True, default="")),
                ("status", models.CharField(choices=[("todo", "To Do"), ("in_progress", "In Progress"), ("done", "Done")], default="todo", max_length=20)),
                ("target_date", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "coach",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="coaching_plans",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "coachee",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="plans",
                        to="api.coachee",
                    ),
                ),
            ],
            options={"ordering": ["target_date"]},
        ),
        # Add plan FK and order to Task
        migrations.AddField(
            model_name="task",
            name="plan",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="actions",
                to="api.coachingplan",
            ),
        ),
        migrations.AddField(
            model_name="task",
            name="order",
            field=models.PositiveIntegerField(default=0),
        ),
        # Add plan FK and mentions to Message
        migrations.AddField(
            model_name="message",
            name="plan",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="messages",
                to="api.coachingplan",
            ),
        ),
        migrations.AddField(
            model_name="message",
            name="mentions",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
    ]
