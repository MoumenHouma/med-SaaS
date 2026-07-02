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
        # SQLite's default busy-timeout is effectively 0, so a second writer
        # gets an immediate "database is locked" OperationalError instead of
        # waiting -- raise it so concurrent writers queue instead of failing.
        # transaction_mode="IMMEDIATE" avoids a separate SQLite deadlock class:
        # with the default deferred BEGIN, two connections that each read
        # inside their transaction.atomic() block before writing can both end
        # up holding a SHARED lock and fail to upgrade to a write lock
        # instantly (busy_timeout doesn't help with that specific deadlock).
        # BEGIN IMMEDIATE takes the write lock upfront instead. Exercised
        # directly by the threaded double-booking regression test in
        # apps/scheduling/tests/test_views.py.
        "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"},
        # File-based (not Django's default :memory:) so that multiple threads/
        # connections in the same test process share one database -- required
        # for that same threaded test, since separate :memory: connections
        # would each be a private, isolated database.
        "TEST": {
            "NAME": BASE_DIR / "test_db.sqlite3",  # noqa: F405
        },
    }
}

# Allow all hosts in development
ALLOWED_HOSTS = ["*"]

# Django Debug Toolbar can be added here later
INTERNAL_IPS = ["127.0.0.1"]

# Email backend: print emails to the console in development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
