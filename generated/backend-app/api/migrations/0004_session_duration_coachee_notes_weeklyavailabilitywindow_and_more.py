from __future__ import annotations

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0003_coachingplan_coachee_task_plan_task_order_message_plan_message_mentions"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="session",
            name="coachee",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sessions",
                to="api.coachee",
            ),
        ),
        migrations.AddField(
            model_name="session",
            name="duration_minutes",
            field=models.PositiveIntegerField(default=60),
        ),
        migrations.AddField(
            model_name="session",
            name="notes",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.CreateModel(
            name="UnavailablePeriod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("start_at", models.DateTimeField()),
                ("end_at", models.DateTimeField()),
                ("reason", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "coach",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="unavailable_periods",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["start_at"]},
        ),
        migrations.CreateModel(
            name="WeeklyAvailabilityWindow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "weekday",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Monday"),
                            (1, "Tuesday"),
                            (2, "Wednesday"),
                            (3, "Thursday"),
                            (4, "Friday"),
                            (5, "Saturday"),
                            (6, "Sunday"),
                        ]
                    ),
                ),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "coach",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="weekly_availability_windows",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["weekday", "start_time"]},
        ),
    ]
