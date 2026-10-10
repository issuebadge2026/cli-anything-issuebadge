"""issuebadge_backend.py — HTTP client for the IssueBadge REST API.

Reads ISSUEBADGE_API_KEY (required) and ISSUEBADGE_BASE_URL (optional,
defaults to https://app.issuebadge.com) from the environment and exposes a
small client used by the core modules. No SDK dependency: every call is a
plain HTTPS request against /api/v1.
"""

from __future__ import annotations

import os
from typing import Any

import requests

VERSION = "1.0.0"
DEFAULT_BASE_URL = "https://app.issuebadge.com"
API_PREFIX = "/api/v1"
DEFAULT_TIMEOUT = 120  # certificate rendering can take a while

API_KEY_HELP = (
    "ISSUEBADGE_API_KEY environment variable is not set.\n"
    "Create a key at https://app.issuebadge.com (Developer → API keys) and run:\n"
    '  export ISSUEBADGE_API_KEY="your-api-key"'
)


class ApiError(RuntimeError):
    """Raised when the API returns a non-success response."""

    def __init__(self, message: str, status: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status = status
        self.payload = payload if isinstance(payload, dict) else {}

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"error": str(self)}
        if self.status is not None:
            out["status"] = self.status
        if self.payload.get("errors"):
            out["errors"] = self.payload["errors"]
        return out


def get_api_key() -> str:
    key = os.environ.get("ISSUEBADGE_API_KEY", "").strip()
    if not key:
        raise RuntimeError(API_KEY_HELP)
    return key


def get_base_url(override: str | None = None) -> str:
    url = override or os.environ.get("ISSUEBADGE_BASE_URL", "").strip() or DEFAULT_BASE_URL
    return url.rstrip("/")


class IssueBadgeClient:
    """Minimal authenticated client for the IssueBadge API."""

    def __init__(self, api_key: str, base_url: str, timeout: int = DEFAULT_TIMEOUT):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout

    def _headers(self, raw: bool) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "*/*" if raw else "application/json",
            "User-Agent": f"cli-anything-issuebadge/{VERSION}",
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        raw: bool = False,
    ) -> Any:
        """Send a request to /api/v1<path>.

        Returns the parsed JSON body, or the raw bytes when ``raw=True`` and the
        server replied with a non-JSON body (PDF, PNG, SVG).

        Raises:
            ApiError: on transport failure, non-2xx status, or ``success: false``.
        """
        url = f"{self.base_url}{API_PREFIX}{path}"
        try:
            resp = requests.request(
                method.upper(),
                url,
                headers=self._headers(raw),
                params=params or None,
                json=json,
                data=data,
                files=files,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ApiError(f"Could not reach {url}: {exc}") from exc

        content_type = resp.headers.get("Content-Type", "")
        if raw and resp.ok and "json" not in content_type:
            return resp.content

        payload = _parse_json(resp)
        if not resp.ok or (isinstance(payload, dict) and payload.get("success") is False):
            raise ApiError(_error_message(resp.status_code, payload), resp.status_code, payload)
        return payload


def _parse_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        text = resp.text.strip()
        if not text or text.startswith("<"):
            # Empty or HTML error page (e.g. a framework 500): fall back to the status code.
            return {}
        return {"message": text[:300]}


def _error_message(status: int, payload: Any) -> str:
    if isinstance(payload, dict):
        msg = payload.get("message") or payload.get("error")
        if msg:
            if payload.get("errors"):
                details = "; ".join(
                    f"{field}: {' '.join(msgs) if isinstance(msgs, list) else msgs}"
                    for field, msgs in payload["errors"].items()
                )
                return f"{msg} ({details})"
            return str(msg)
    if status == 401:
        return "Unauthorized: invalid or missing ISSUEBADGE_API_KEY"
    return f"HTTP {status}"


def get_client(base_url: str | None = None) -> IssueBadgeClient:
    """Return an authenticated client, or raise RuntimeError when no key is set."""
    return IssueBadgeClient(api_key=get_api_key(), base_url=get_base_url(base_url))


def check_connectivity(base_url: str | None = None) -> dict[str, Any]:
    """Validate the API key against POST /validate-key.

    Returns a dict with keys: ok (bool), message (str) and, on success,
    token_type / user / base_url.
    """
    try:
        client = get_client(base_url)
        payload = client.request("POST", "/validate-key")
        return {
            "ok": True,
            "message": payload.get("message", "API key is valid"),
            "token_type": payload.get("token_type"),
            "user": payload.get("user"),
            "base_url": client.base_url,
        }
    except RuntimeError as exc:
        return {"ok": False, "message": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": f"IssueBadge API error: {exc}"}
