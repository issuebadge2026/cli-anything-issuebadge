"""qrcodes.py — dynamic QR code operations (/qrcode/*)."""

from __future__ import annotations

from typing import Any

from cli_anything.issuebadge.utils.issuebadge_backend import IssueBadgeClient

QR_TYPES = (
    "url", "text", "email", "phone", "sms", "wifi", "vcard", "mecard",
    "maps", "event", "paypal", "facebook", "twitter", "youtube",
)


def list_qrcodes(
    client: IssueBadgeClient, qr_type: str | None = None, page: int = 1, per_page: int = 20
) -> dict[str, Any]:
    params: dict[str, Any] = {"page": page, "per_page": per_page}
    if qr_type:
        params["type"] = qr_type
    return client.request("GET", "/qrcode", params=params)


def create_qrcode(
    client: IssueBadgeClient, name: str, qr_type: str, data: dict[str, str], is_active: bool = True
) -> dict[str, Any]:
    return client.request(
        "POST", "/qrcode/create", json={"name": name, "type": qr_type, "data": data, "is_active": is_active}
    )


def get_qrcode(client: IssueBadgeClient, code: str) -> dict[str, Any]:
    return client.request("GET", f"/qrcode/{code}")


def update_qrcode(
    client: IssueBadgeClient,
    code: str,
    name: str | None = None,
    data: dict[str, str] | None = None,
    is_active: bool | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if name:
        body["name"] = name
    if data:
        body["data"] = data
    if is_active is not None:
        body["is_active"] = is_active
    if not body:
        raise RuntimeError("Nothing to update: pass --name, --data and/or --active/--inactive")
    return client.request("PATCH", f"/qrcode/{code}", json=body)


def list_scans(client: IssueBadgeClient, code: str, page: int = 1, per_page: int = 50) -> dict[str, Any]:
    return client.request("GET", f"/qrcode/{code}/scans", params={"page": page, "per_page": per_page})


def delete_qrcode(client: IssueBadgeClient, code: str) -> dict[str, Any]:
    return client.request("DELETE", f"/qrcode/{code}")


def download_image(
    client: IssueBadgeClient, code: str, out_path: str, size: int = 500, fmt: str = "png"
) -> dict[str, Any]:
    content = client.request("GET", f"/qrcode/{code}/image", params={"size": size, "format": fmt}, raw=True)
    with open(out_path, "wb") as fh:
        fh.write(content)
    return {"ok": True, "path": out_path, "bytes": len(content), "format": fmt, "size": size}
