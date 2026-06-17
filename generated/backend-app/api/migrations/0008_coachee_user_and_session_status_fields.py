from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0007_rename_api_unavail_coach_i_761992_idx_api_unavail_coach_i_6b2239_idx_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="coachee",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="coachee_profiles",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="session",
            name="response_note",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="session",
            name="status",
            field=models.CharField(
                choices=[
                    ("requested", "Requested"),
                    ("accepted", "Accepted"),
                    ("proposed", "Proposed new time"),
                    ("rejected", "Rejected"),
                ],
                default="accepted",
                max_length=20,
            ),
        ),
    ]
