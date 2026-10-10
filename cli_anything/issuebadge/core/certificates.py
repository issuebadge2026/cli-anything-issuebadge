"""certificates.py — rendered certificate PDFs (/certificate/*)."""

from __future__ import annotations

from typing import Any

from cli_anything.issuebadge.utils.issuebadge_backend import IssueBadgeClient


def _write(path: str, content: bytes) -> dict[str, Any]:
    with open(path, "wb") as fh:
        fh.write(content)
    return {"ok": True, "path": path, "bytes": len(content)}


def download_certificate(client: IssueBadgeClient, issue_id: str, out_path: str) -> dict[str, Any]:
    """Render the certificate for one issued badge and save the PDF."""
    content = client.request("POST", "/certificate/generate", json={"issued_badge_uuid": issue_id}, raw=True)
    return _write(out_path, content)


def download_batch(client: IssueBadgeClient, issue_ids: list[str], out_path: str) -> dict[str, Any]:
    """Render several certificates into one merged PDF and save it."""
    content = client.request(
        "POST", "/certificate/batch/generate", json={"issued_badge_uuids": list(issue_ids)}, raw=True
    )
    result = _write(out_path, content)
    result["count"] = len(issue_ids)
    return result
