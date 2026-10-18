"""Pytest bootstrap. Sets the admin token before the app is imported."""

from __future__ import annotations

import os

os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
os.environ.setdefault("FALKORDB_HOST", "localhost")
