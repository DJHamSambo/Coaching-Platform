from __future__ import annotations

import hashlib
import logging
import re
import secrets
import string
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from django.utils.html import escape

from api.models import Coachee, EmailVerificationToken, UserProfile

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


def mark_email_verified(user: User, value: bool = True) -> None:
    """Record whether the user has confirmed their email address."""
    UserProfile.objects.update_or_create(user=user, defaults={"email_verified": value})


def hash_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest used to look up a stored token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_activation_token(
    user: User, *, purpose: str = EmailVerificationToken.PURPOSE_ACTIVATION
) -> str:
    """Issue a fresh single-use activation token for the user.

    Any previously issued, still-unused tokens for the same purpose are
    invalidated so only the latest link works. Returns the raw token (emailed to
    the user); only its hash is persisted.
    """
    EmailVerificationToken.objects.filter(
        user=user, purpose=purpose, used_at__isnull=True
    ).update(used_at=timezone.now())

    raw_token = secrets.token_urlsafe(48)
    ttl_hours = getattr(settings, "ACCOUNT_ACTIVATION_TOKEN_TTL_HOURS", 72)
    EmailVerificationToken.objects.create(
        user=user,
        token_hash=hash_token(raw_token),
        purpose=purpose,
        expires_at=timezone.now() + timedelta(hours=ttl_hours),
    )
    return raw_token


def build_activation_link(raw_token: str, *, next_step: str | None = None) -> str:
    """Build the SPA activation URL that carries the raw token.

    ``next_step`` optionally names a step the SPA should take the user to right
    after they sign in for the first time (e.g. ``"questionnaire"``).
    """
    base = getattr(settings, "ACCOUNT_ACTIVATION_URL", "") or ""
    params = {"token": raw_token}
    if next_step:
        params["next"] = next_step
    return f"{base}?{urlencode(params)}"


def send_activation_email(
    *, user: User, raw_token: str, role: str, request_questionnaire: bool = False
) -> None:
    """Email a secure activation link so the user can verify and set a password.

    When ``request_questionnaire`` is set for a coachee, the email also
    explains that their coach has requested a foundational questionnaire and
    links them straight to it once they've activated and signed in.

    No password is ever transmitted. Never raises — email failures are logged so
    they don't block account provisioning.
    """
    recipient = (user.email or "").strip()
    if not recipient:
        logger.warning("No email on record for %s; skipping activation email.", user.username)
        return

    role_label = "coach" if role == "coach" else "coachee"
    include_questionnaire = request_questionnaire and role == "coachee"
    greeting_name = (user.get_full_name() or user.username).strip()
    activation_link = build_activation_link(raw_token, next_step="questionnaire" if include_questionnaire else None)
    ttl_hours = getattr(settings, "ACCOUNT_ACTIVATION_TOKEN_TTL_HOURS", 72)

    text_lines = [
        f"Hi {greeting_name},",
        "",
        f"An account has been created for you on the Coaching Platform as a {role_label}.",
        "",
        "To activate your account, confirm your email address and choose a password,",
        "open the link below:",
        "",
        activation_link,
        "",
    ]
    if include_questionnaire:
        text_lines += [
            "Your coach has also requested that you complete a short foundational",
            "questionnaire to help them prepare for your coaching sessions. Once you",
            "activate your account and sign in using the link above, you'll be taken",
            "straight to it \u2014 you can also find it any time under your Profile tab.",
            "",
        ]
    text_lines += [
        f"This link is valid for {ttl_hours} hours and can only be used once.",
        "If you didn't expect this email, you can safely ignore it.",
        "",
        "The Coaching Platform team",
    ]
    text_body = "\n".join(text_lines)

    safe_name = escape(greeting_name)
    safe_link = escape(activation_link)
    questionnaire_html = ""
    if include_questionnaire:
        questionnaire_html = """\
  <p>Your coach has also requested that you complete a short <strong>foundational
     questionnaire</strong> to help them prepare for your coaching sessions. Once you
     activate your account and sign in, you'll be taken straight to it — you can
     also find it any time under your Profile tab.</p>
"""
    html_body = f"""\
<div style="font-family:Segoe UI,Arial,sans-serif;color:#1f2933;line-height:1.5">
  <p>Hi {safe_name},</p>
  <p>An account has been created for you on the <strong>Coaching Platform</strong>
     as a {role_label}.</p>
  <p>To activate your account, confirm your email address, and choose a password,
     click the button below.</p>
  <p style="margin:24px 0">
    <a href="{safe_link}"
       style="background:#2563eb;color:#ffffff;text-decoration:none;padding:12px 20px;
              border-radius:8px;font-weight:600;display:inline-block">
      Verify email &amp; set password
    </a>
  </p>
{questionnaire_html}\
  <p style="font-size:0.9em;color:#52606d">
    Or paste this link into your browser:<br>
    <a href="{safe_link}">{safe_link}</a>
  </p>
  <p style="font-size:0.85em;color:#7b8794">
    This link is valid for {ttl_hours} hours and can only be used once.
    If you didn't expect this email, you can safely ignore it.
  </p>
  <p style="font-size:0.85em;color:#7b8794">The Coaching Platform team</p>
</div>"""

    try:
        message = EmailMultiAlternatives(
            subject="Activate your Coaching Platform account",
            body=text_body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=[recipient],
        )
        message.attach_alternative(html_body, "text/html")
        message.send(fail_silently=False)
    except Exception:  # pragma: no cover - transport failures shouldn't block provisioning
        logger.exception("Failed to send activation email to %s", recipient)


def provision_coach_login(user: User) -> None:
    """Prepare a freshly created coach for activation.

    The account is left inactive with an unusable password until the coach
    verifies their email and sets a password via the emailed activation link.
    """
    user.set_unusable_password()
    if user.is_active:
        user.is_active = False
    user.save(update_fields=["password", "is_active"])
    mark_email_verified(user, False)
    raw_token = create_activation_token(user)
    send_activation_email(user=user, raw_token=raw_token, role="coach")


def provision_coachee_login(coachee: Coachee, *, request_questionnaire: bool = True) -> User | None:
    """Create an inactive login account for a coachee and email an activation link.

    When ``request_questionnaire`` is set, the activation email also explains
    that a foundational questionnaire is expected and links straight to it.

    Returns the created ``User`` or ``None`` if no account was provisioned
    (e.g. the coachee already has one or has no email address).
    """
    if coachee.user_id or not (coachee.email or "").strip():
        return None

    email = coachee.email.strip()
    base = email.split("@", 1)[0] or coachee.name
    username = _unique_username(base)

    user = User.objects.create_user(username=username, email=email)
    user.set_unusable_password()
    user.is_active = False

    name_parts = (coachee.name or "").split(" ", 1)
    if name_parts and name_parts[0]:
        user.first_name = name_parts[0][:150]
        if len(name_parts) > 1:
            user.last_name = name_parts[1][:150]
    user.save()

    coachee.user = user
    coachee.save(update_fields=["user"])

    mark_email_verified(user, False)
    raw_token = create_activation_token(user)
    send_activation_email(
        user=user, raw_token=raw_token, role="coachee", request_questionnaire=request_questionnaire
    )
    return user
