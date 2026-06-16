from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0005_alter_task_options_alter_coachee_id_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="session",
            name="coachee",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="coachee_sessions",
                to="api.coachee",
            ),
        ),
        migrations.AddIndex(
            model_name="weeklyavailabilitywindow",
            index=models.Index(fields=["coach", "weekday", "start_time"], name="api_weeklya_coach_i_2d8f5d_idx"),
        ),
        migrations.AddIndex(
            model_name="unavailableperiod",
            index=models.Index(fields=["coach", "start_at", "end_at"], name="api_unavail_coach_i_761992_idx"),
        ),
    ]
