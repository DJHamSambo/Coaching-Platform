from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0008_coachee_user_and_session_status_fields"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="session",
            name="response_note",
        ),
        migrations.RemoveField(
            model_name="session",
            name="status",
        ),
    ]
