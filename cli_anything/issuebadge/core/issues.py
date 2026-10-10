"""issues.py — issued badge / certificate operations (/issue/*)."""

from __future__ import annotations

import csv
from typing import Any

from cli_anything.issuebadge.utils.issuebadge_backend import ApiError, IssueBadgeClient

# CSV columns that map to API fields; every other column becomes metadata.
_RESERVED_COLUMNS = ("name", "email", "issue_date", "expire_date", "memo", "idempotency_key")


def _compact(body: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in body.items() if v not in (None, "", {}, [])}


def issue_badge(
    client: IssueBadgeClient,
    badge_id: str,
    name: str,
    email: str | None = None,
    idempotency_key: str | None = None,
    issue_date: str | None = None,
    expire_date: str | None = None,
    memo: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = _compact(
        {
            "badge_id": badge_id,
            "name": name,
            "email": email,
            "idempotency_key": idempotency_key,
            "issue_date": issue_date,
            "expire_date": expire_date,
            "memo": memo,
            "metadata": metadata,
        }
    )
    return client.request("POST", "/issue/create", json=body)


def list_issues(
    client: IssueBadgeClient,
    badge_id: str | None = None,
    recipient_name: str | None = None,
    recipient_email: str | None = None,
    page: int = 1,
    per_page: int = 10,
) -> dict[str, Any]:
    params = _compact(
        {
            "badge_id": badge_id,
            "recipient_name": recipient_name,
            "recipient_email": recipient_email,
            "page": page,
            "per_page": per_page,
        }
    )
    return client.request("GET", "/issue/get", params=params)


def get_issue(client: IssueBadgeClient, issue_id: str) -> dict[str, Any]:
    return client.request("GET", f"/issue/get/{issue_id}")


def get_history(client: IssueBadgeClient, issue_id: str) -> dict[str, Any]:
    return client.request("GET", f"/issue/{issue_id}/history")


def revoke_issue(
    client: IssueBadgeClient,
    issue_id: str,
    reason: str | None = None,
    comments: str | None = None,
) -> dict[str, Any]:
    body = _compact({"issue_id": issue_id, "reason": reason, "comments": comments})
    return client.request("POST", "/issue/revoke", json=body)


def update_issue(
    client: IssueBadgeClient,
    issue_id: str,
    expire_date: str | None = None,
    memo: str | None = None,
    reinstate: bool = False,
) -> dict[str, Any]:
    body = _compact({"expire_date": expire_date, "memo": memo})
    if reinstate:
        body["reinstate"] = True
    if not body:
        raise RuntimeError("Nothing to update: pass --expire-date, --memo and/or --reinstate")
    return client.request("PATCH", f"/issue/{issue_id}", json=body)


def read_recipients_csv(path: str) -> list[dict[str, str]]:
    """Read a recipients CSV. Requires a ``name`` column; ``email``, ``issue_date``,
    ``expire_date``, ``memo`` and ``idempotency_key`` are optional; any other
    column is sent as metadata (custom field values)."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or "name" not in reader.fieldnames:
            raise RuntimeError(f"{path}: CSV must have a header row with a 'name' column")
        rows = [{k.strip(): (v or "").strip() for k, v in row.items() if k} for row in reader]
    if not rows:
        raise RuntimeError(f"{path}: CSV has no recipient rows")
    return rows


def bulk_issue(
    client: IssueBadgeClient,
    badge_id: str,
    rows: list[dict[str, str]],
    idempotency_prefix: str | None = None,
) -> dict[str, Any]:
    """Issue one badge per CSV row. Never stops on a failed row; the summary
    lists every outcome so the caller can retry only the failures."""
    results: list[dict[str, Any]] = []
    issued = failed = 0
    for index, row in enumerate(rows, start=1):
        metadata = {k: v for k, v in row.items() if k not in _RESERVED_COLUMNS and v != ""}
        key = row.get("idempotency_key") or (f"{idempotency_prefix}-{index}" if idempotency_prefix else None)
        entry: dict[str, Any] = {"row": index, "name": row.get("name", ""), "email": row.get("email", "")}
        try:
            if not row.get("name"):
                raise RuntimeError("name is empty")
            result = issue_badge(
                client,
                badge_id,
                name=row["name"],
                email=row.get("email") or None,
                idempotency_key=key,
                issue_date=row.get("issue_date") or None,
                expire_date=row.get("expire_date") or None,
                memo=row.get("memo") or None,
                metadata=metadata or None,
            )
            entry.update(ok=True, issue_id=result.get("IssueId"), public_url=result.get("publicUrl"))
            issued += 1
        except (ApiError, RuntimeError) as exc:
            entry.update(ok=False, error=str(exc))
            failed += 1
        results.append(entry)
    return {"ok": failed == 0, "total": len(rows), "issued": issued, "failed": failed, "results": results}
