"""organizations.py — issuing organisation operations (/organization/*)."""

from __future__ import annotations

from typing import Any

from cli_anything.issuebadge.utils.issuebadge_backend import IssueBadgeClient


def list_organizations(client: IssueBadgeClient) -> dict[str, Any]:
    # The API exposes the listing as POST.
    return client.request("POST", "/organization/getall")


def create_organization(client: IssueBadgeClient, name: str, description: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"name": name}
    if description:
        body["description"] = description
    return client.request("POST", "/organization/create", json=body)
