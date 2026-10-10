"""badges.py — badge template operations (/badge/*)."""

from __future__ import annotations

import os
from typing import Any

from cli_anything.issuebadge.utils.issuebadge_backend import IssueBadgeClient


def list_badges(client: IssueBadgeClient) -> dict[str, Any]:
    return client.request("GET", "/badge/getall")


def get_badge(client: IssueBadgeClient, badge_id: str) -> dict[str, Any]:
    return client.request("GET", f"/badge/{badge_id}")


def create_badge(client: IssueBadgeClient, name: str, description: str, logo_path: str) -> dict[str, Any]:
    """Create a badge template. The logo is uploaded as multipart/form-data."""
    with open(logo_path, "rb") as fh:
        return client.request(
            "POST",
            "/badge/create",
            data={"name": name, "description": description},
            files={"badge_logo": (os.path.basename(logo_path), fh)},
        )
