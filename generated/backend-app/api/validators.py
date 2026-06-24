from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class PasswordComplexityValidator:
    """Enforce current best-practice password length and complexity.

    Requires a minimum length plus a mix of character classes (uppercase,
    lowercase, digit, and a special character). Configure ``min_length`` via
    the validator ``OPTIONS`` in ``AUTH_PASSWORD_VALIDATORS``.
    """

    def __init__(self, min_length: int = 12):
        self.min_length = min_length

    def validate(self, password: str, user=None) -> None:
        missing: list[str] = []

        if len(password) < self.min_length:
            missing.append(_("at least %(n)d characters") % {"n": self.min_length})
        if not re.search(r"[A-Z]", password):
            missing.append(_("an uppercase letter"))
        if not re.search(r"[a-z]", password):
            missing.append(_("a lowercase letter"))
        if not re.search(r"\d", password):
            missing.append(_("a number"))
        if not re.search(r"[^A-Za-z0-9]", password):
            missing.append(_("a special character"))

        if missing:
            raise ValidationError(
                _("Password must contain %(requirements)s.") % {"requirements": ", ".join(missing)},
                code="password_too_weak",
            )

    def get_help_text(self) -> str:
        return _(
            "Your password must be at least %(n)d characters and include an uppercase "
            "letter, a lowercase letter, a number, and a special character."
        ) % {"n": self.min_length}
