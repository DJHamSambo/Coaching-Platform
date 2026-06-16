from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0001_initial"),
    ]

    # `task_id` already exists in `0001_initial`; keep this migration as a no-op
    # to preserve historical ordering without failing on fresh databases.
    operations = []
