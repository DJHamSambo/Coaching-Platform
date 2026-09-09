"""Idempotently seed the initial staff (admin) user on deployed environments.

Runs at App Service startup (see the appCommandLine in appService.bicep). The
username and password come from the DJANGO_ADMIN_USERNAME / DJANGO_ADMIN_PASSWORD
environment variables; when either is missing the command is a no-op, so local
development and tests are unaffected. The created account has must_reset_password
set, so the first browser login forces a password change.
"""

import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from api.models import UserProfile


class Command(BaseCommand):
    help = "Create the initial staff user from DJANGO_ADMIN_USERNAME/DJANGO_ADMIN_PASSWORD if it does not exist."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_ADMIN_USERNAME", "").strip()
        password = os.environ.get("DJANGO_ADMIN_PASSWORD", "")
        if not username or not password:
            self.stdout.write("DJANGO_ADMIN_USERNAME/DJANGO_ADMIN_PASSWORD not set; skipping admin seed.")
            return

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"is_staff": True, "is_superuser": True, "is_active": True},
        )
        if not created:
            self.stdout.write(f"Staff user '{username}' already exists; leaving it unchanged.")
            return

        user.set_password(password)
        user.save(update_fields=["password"])
        UserProfile.objects.get_or_create(user=user, defaults={"must_reset_password": True})
        self.stdout.write(f"Created staff user '{username}' (password reset required on first login).")
