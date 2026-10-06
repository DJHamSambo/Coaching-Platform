from django.db import migrations


def backfill(apps, schema_editor):
    Coachee = apps.get_model("api", "Coachee")
    FoundationalQuestionnaire = apps.get_model("api", "FoundationalQuestionnaire")

    # Coachees whose login was provisioned but never activated haven't consented
    # to the relationship yet; activating their account will make it active.
    Coachee.objects.filter(
        user__isnull=False, user__is_active=False, user__last_login__isnull=True
    ).update(status="invited")

    # Questionnaires predate relationships. Attribute each to the owner's
    # earliest relationship, which is the coach who originally requested it.
    for questionnaire in FoundationalQuestionnaire.objects.filter(coachee__isnull=True):
        relationship = (
            Coachee.objects.filter(user_id=questionnaire.owner_id).order_by("created_at", "id").first()
        )
        if relationship is not None:
            questionnaire.coachee_id = relationship.id
            questionnaire.save(update_fields=["coachee"])


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0025_multi_coach_relationships"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
