"""
Rendia — Local Development Settings
Uses SQLite for zero-configuration local dev. Do NOT use in production.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

# SQLite for local dev — no setup required
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}

# Allow all hosts in development
ALLOWED_HOSTS = ["*"]

# Django Debug Toolbar can be added here later
INTERNAL_IPS = ["127.0.0.1"]

# Email backend: print emails to the console in development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
