from __future__ import annotations

import logging
import re
import secrets
import string

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail

from api.models import Coachee, UserProfile

logger = logging.getLogger(__name__)

_SPECIALS = "!@#$%^&*-_=+"
_ALL_CHARS = string.ascii_lowercase + string.ascii_uppercase + string.digits + _SPECIALS


def generate_temp_password(length: int = 16) -> str:
    """Generate a cryptographically random temporary password.

    The result always contains an uppercase letter, a lowercase letter, a
    digit, and a special character so it satisfies the platform's password
    complexity policy.
    """
    if length < 12:
        length = 12

    chars = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(_SPECIALS),
    ]
    chars += [secrets.choice(_ALL_CHARS) for _ in range(length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def _unique_username(base: str) -> str:
    """Build a unique, sanitized username from an arbitrary string."""
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "", base or "").strip("._-").lower()
    cleaned = cleaned[:140] or "user"

    candidate = cleaned
    counter = 1
    while User.objects.filter(username=candidate).exists():
        counter += 1
        suffix = str(counter)
        candidate = f"{cleaned[: 140 - len(suffix)]}{suffix}"
    return candidate


def mark_must_reset_password(user: User, value: bool = True) -> None:
    """Flag (or clear) that the user must reset their password on next login."""
    UserProfile.objects.update_or_create(user=user, defaults={"must_reset_password": value})


def send_welcome_email(*, user: User, temp_password: str, role: str) -> None:
    """Send a welcome email with temporary credentials. Never raises."""
    recipient = (user.email or "").strip()
    if not recipient:
        logger.warning("No email on record for %s; skipping welcome email.", user.username)
        return

    role_label = "coach" if role == "coach" else "coachee"
    login_url = getattr(settings, "FRONTEND_LOGIN_URL", "")
    greeting_name = (user.get_full_name() or user.username).strip()

    lines = [
        f"Hi {greeting_name},",
        "",
        f"Welcome to the Coaching Platform! An account has been created for you as a {role_label}.",
        "",
        "Use these temporary credentials to sign in:",
        f"    Username: {user.username}",
        f"    Temporary password: {temp_password}",
        "",
    ]
    if login_url:
        lines += [f"Sign in here: {login_url}", ""]
    lines += [
        "For your security, you'll be asked to choose a new password the first time you sign in.",
        "",
        "See you inside,",
        "The Coaching Platform team",
    ]

    try:
        send_mail(
            subject="Welcome to the Coaching Platform",
            message="\n".join(lines),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception:  # pragma: no cover - email transport failures shouldn't block provisioning
        logger.exception("Failed to send welcome email to %s", recipient)


def provision_coach_login(user: User) -> str:
    """Assign a temporary password to a freshly created coach and email it.

    Returns the generated temporary password (for logging/testing only — it is
    never returned through the API).
    """
    temp_password = generate_temp_password()
    user.set_password(temp_password)
    user.save(update_fields=["password"])
    mark_must_reset_password(user, True)
    send_welcome_email(user=user, temp_password=temp_password, role="coach")
    return temp_password


def provision_coachee_login(coachee: Coachee) -> User | None:
    """Create a login account for a coachee that has an email but no user yet.

    Returns the created ``User`` or ``None`` if no account was provisioned
    (e.g. the coachee already has one or has no email address).
    """
    if coachee.user_id or not (coachee.email or "").strip():
        return None

    email = coachee.email.strip()
    base = email.split("@", 1)[0] or coachee.name
    username = _unique_username(base)
    temp_password = generate_temp_password()

    user = User.objects.create_user(username=username, email=email, password=temp_password)

    name_parts = (coachee.name or "").split(" ", 1)
    if name_parts and name_parts[0]:
        user.first_name = name_parts[0][:150]
        if len(name_parts) > 1:
            user.last_name = name_parts[1][:150]
        user.save(update_fields=["first_name", "last_name"])

    coachee.user = user
    coachee.save(update_fields=["user"])

    mark_must_reset_password(user, True)
    send_welcome_email(user=user, temp_password=temp_password, role="coachee")
    return user
