from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0021_coachingcontract"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="phone",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional contact phone number shown on the account profile.",
                max_length=40,
            ),
        ),
    ]
