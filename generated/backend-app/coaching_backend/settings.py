from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from a .env file (repository root first, then a
# backend-local override) so secrets like RESEND_API_KEY are available without
# exporting them manually. Safe no-op if python-dotenv isn't installed.
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR.parent.parent / ".env")
    load_dotenv(BASE_DIR / ".env")
except ImportError:  # pragma: no cover - dotenv is an optional convenience
    pass


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
# Use a strong secret from the environment for signing sessions and JWTs. The
# fallback below is only for local development and is intentionally long enough
# (>= 32 bytes) to satisfy the JWT HMAC key-length requirement.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or (
    "dev-insecure-6f4c2b8e1a9d7c035e82f1a4b6d09c7e3f1a5b8c2d4e6f70-change-me"
)
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

CORS_ALLOWED_ORIGINS = ["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5176", "http://localhost:4173"]

ROOT_URLCONF = "coaching_backend.urls"
WSGI_APPLICATION = "coaching_backend.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
}

# Uploaded documents (coaching resources)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Password policy (current best-practice length + complexity)
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {
        "NAME": "api.validators.PasswordComplexityValidator",
        "OPTIONS": {"min_length": 12},
    },
]

# Email configuration (driven by environment variables).
# Delivery backend priority:
#   1. An explicit EMAIL_BACKEND override, if provided.
#   2. Resend HTTP API when RESEND_API_KEY is set (recommended).
#   3. SMTP when EMAIL_HOST is configured.
#   4. Console backend for local development (messages printed to the log).
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
_smtp_configured = bool(os.environ.get("EMAIL_HOST"))
if os.environ.get("EMAIL_BACKEND"):
    EMAIL_BACKEND = os.environ["EMAIL_BACKEND"]
elif RESEND_API_KEY:
    EMAIL_BACKEND = "api.email_backends.ResendEmailBackend"
elif _smtp_configured:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "10"))
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL", "Coaching Platform <onboarding@resend.dev>"
)

# Public base URL of the SPA, used to build links in outbound emails.
FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://localhost:5173")
# Used to build the sign-in link included in emails
FRONTEND_LOGIN_URL = os.environ.get("FRONTEND_LOGIN_URL", FRONTEND_BASE_URL)
# Where the account-activation link points (the SPA reads the ?token= query).
ACCOUNT_ACTIVATION_URL = os.environ.get(
    "ACCOUNT_ACTIVATION_URL", f"{FRONTEND_BASE_URL.rstrip('/')}/activate"
)
# How long an activation/verification link stays valid.
ACCOUNT_ACTIVATION_TOKEN_TTL_HOURS = int(
    os.environ.get("ACCOUNT_ACTIVATION_TOKEN_TTL_HOURS", "72")
)

CALENDAR_PAGE_SIZE = 100
CALENDAR_MAX_PAGE_SIZE = 500

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
