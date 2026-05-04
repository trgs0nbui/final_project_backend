import django
from django.conf import settings


def pytest_configure(config):
    """Override database to use SQLite in-memory for fast test runs."""
    settings.DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
