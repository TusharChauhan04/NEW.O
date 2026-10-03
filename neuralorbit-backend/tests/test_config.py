"""
Tests for the fail-closed guard added to close BUG-08 (AUTH_REQUIRED and
APP_ENV both default to permissive values — nothing previously stopped a
production deployment from silently inheriting that).
"""

import pytest

from app.config import Settings, InsecureConfigError, validate_production_config


def test_dev_defaults_are_unchanged_and_allowed():
    s = Settings(APP_ENV="development", AUTH_REQUIRED=False)
    validate_production_config(s)  # must not raise


def test_production_without_auth_required_is_refused():
    s = Settings(APP_ENV="production", AUTH_REQUIRED=False)
    with pytest.raises(InsecureConfigError):
        validate_production_config(s)


def test_production_with_auth_required_is_allowed():
    s = Settings(APP_ENV="production", AUTH_REQUIRED=True)
    validate_production_config(s)  # must not raise
