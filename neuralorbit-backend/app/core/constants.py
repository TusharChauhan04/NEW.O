"""
core/constants.py — Shared validation constants.

VALID_MODULES was previously defined only in events.py and enforced there;
decisions.py and integrations.py accepted arbitrary module strings. Centralized
here so all three routers validate against the same set.
"""

VALID_MODULES = {"crm", "marketing", "shield", "website", "neural-orbit"}
