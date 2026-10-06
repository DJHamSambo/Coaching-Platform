"""Merge coachee logins that share an email address into a single account.

Before coachees were matched by email, a second coach adding the same person
created a second login. This command folds those duplicates into the oldest
account so the person has one identity across all their coaches.

Dry run by default; pass ``--apply`` to make changes. Only coachee-only
accounts are merged (never coaches/admins). A group is skipped and reported
when two of its accounts have relationships with the same coach, because that
needs a human to decide which relationship to keep.
"""
from __future__ import annotations

from collections import defaultdict

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import Coachee, Resource, UserProfile


def _is_coachee_only(user: User) -> bool:
    return (
        not user.is_staff
        and user.coachee_profiles.exists()
        and not user.coachees.exists()
        and not user.coaching_plans.exists()
    )


def _repoint_user(duplicate: User, primary: User) -> None:
    """Move everything that references ``duplicate`` onto ``primary``."""
    for rel in User._meta.related_objects:
        if rel.one_to_one:
            continue  # UserProfile: keep the primary's
        if rel.many_to_many:
            continue  # handled explicitly below
        rel.related_model._base_manager.filter(**{rel.field.name: duplicate}).update(**{rel.field.name: primary})
    for resource in Resource.objects.filter(shared_with=duplicate):
        resource.shared_with.remove(duplicate)
        resource.shared_with.add(primary)


class Command(BaseCommand):
    help = "Merge duplicate coachee logins that share an email address (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Make the changes instead of only reporting them.")

    def handle(self, *args, apply: bool = False, **options):
        groups: dict[str, list[User]] = defaultdict(list)
        for user in User.objects.exclude(email="").order_by("id"):
            if _is_coachee_only(user):
                groups[user.email.strip().lower()].append(user)

        merged = skipped = 0
        for email, users in groups.items():
            if len(users) < 2:
                continue
            # Keep the account the person actually uses: activated and signed
            # in beats never-activated; ties go to the oldest.
            users.sort(key=lambda u: (not u.is_active, u.last_login is None, u.id))
            primary, duplicates = users[0], users[1:]

            coach_ids = list(
                Coachee.objects.filter(user__in=users).values_list("added_by_id", flat=True)
            )
            if len(coach_ids) != len(set(coach_ids)):
                skipped += 1
                self.stdout.write(self.style.WARNING(
                    f"SKIP {email}: accounts {[u.username for u in users]} have more than one "
                    "relationship with the same coach. Delete the unwanted coachee record, then re-run."
                ))
                continue

            self.stdout.write(
                f"{'MERGE' if apply else 'WOULD MERGE'} {email}: keep {primary.username} (id {primary.id}), "
                f"fold in {[f'{u.username} (id {u.id})' for u in duplicates]}"
            )
            merged += 1
            if not apply:
                continue
            with transaction.atomic():
                for duplicate in duplicates:
                    _repoint_user(duplicate, primary)
                    UserProfile.objects.filter(user=duplicate).delete()
                    # Deactivate rather than delete so the merge is auditable;
                    # clearing the email stops it matching sign-ins or invites.
                    duplicate.is_active = False
                    duplicate.email = ""
                    duplicate.set_unusable_password()
                    duplicate.save(update_fields=["is_active", "email", "password"])

        verb = "Merged" if apply else "Would merge"
        self.stdout.write(self.style.SUCCESS(f"{verb} {merged} group(s); skipped {skipped}."))
