"""
test_core.py — Unit tests for the IssueBadge CLI harness.

All HTTP calls are mocked; no network access and no API key needed.
Run with: pytest cli_anything/issuebadge/tests/test_core.py -v
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cli_anything.issuebadge.issuebadge_cli import cli
from cli_anything.issuebadge.core import issues as issues_core
from cli_anything.issuebadge.utils import issuebadge_backend as backend
from cli_anything.issuebadge.utils.issuebadge_backend import (
    ApiError,
    IssueBadgeClient,
    check_connectivity,
    get_base_url,
    get_client,
)

REQUEST = "cli_anything.issuebadge.utils.issuebadge_backend.requests.request"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("ISSUEBADGE_API_KEY", "test-key")
    monkeypatch.delenv("ISSUEBADGE_BASE_URL", raising=False)


def _resp(status: int = 200, payload=None, content: bytes = b"", content_type: str | None = None):
    resp = MagicMock()
    resp.status_code = status
    resp.ok = 200 <= status < 300
    if payload is not None:
        resp.json.return_value = payload
        resp.text = json.dumps(payload)
        resp.headers = {"Content-Type": content_type or "application/json"}
    else:
        resp.json.side_effect = ValueError("not json")
        resp.text = content.decode("latin-1")
        resp.headers = {"Content-Type": content_type or "application/octet-stream"}
    resp.content = content if payload is None else json.dumps(payload).encode()
    return resp


def _call(mock):
    """Return (method, url, kwargs) of the last mocked request."""
    args, kwargs = mock.call_args
    return args[0], args[1], kwargs


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------

class TestBackend:
    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("ISSUEBADGE_API_KEY")
        with pytest.raises(RuntimeError, match="ISSUEBADGE_API_KEY"):
            get_client()

    def test_default_base_url(self):
        assert get_base_url() == "https://app.issuebadge.com"

    def test_env_base_url_strips_trailing_slash(self, monkeypatch):
        monkeypatch.setenv("ISSUEBADGE_BASE_URL", "https://issuebadge.test/")
        assert get_base_url() == "https://issuebadge.test"

    def test_override_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("ISSUEBADGE_BASE_URL", "https://issuebadge.test")
        assert get_base_url("http://localhost:8000/") == "http://localhost:8000"

    def test_request_sends_bearer_and_prefix(self):
        client = IssueBadgeClient("k", "https://host")
        with patch(REQUEST, return_value=_resp(200, {"success": True, "data": []})) as m:
            out = client.request("GET", "/badge/getall")
        method, url, kwargs = _call(m)
        assert method == "GET"
        assert url == "https://host/api/v1/badge/getall"
        assert kwargs["headers"]["Authorization"] == "Bearer k"
        assert kwargs["headers"]["Accept"] == "application/json"
        assert out == {"success": True, "data": []}

    def test_http_error_maps_to_api_error(self):
        client = IssueBadgeClient("k", "https://host")
        with patch(REQUEST, return_value=_resp(404, {"success": False, "message": "Badge not found"})):
            with pytest.raises(ApiError) as exc:
                client.request("GET", "/badge/x")
        assert exc.value.status == 404
        assert "Badge not found" in str(exc.value)

    def test_validation_errors_are_flattened(self):
        client = IssueBadgeClient("k", "https://host")
        payload = {"success": False, "message": "Validation failed", "errors": {"name": ["The name is required."]}}
        with patch(REQUEST, return_value=_resp(422, payload)):
            with pytest.raises(ApiError) as exc:
                client.request("POST", "/issue/create", json={})
        assert "name: The name is required." in str(exc.value)
        assert exc.value.to_dict()["errors"] == payload["errors"]

    def test_success_false_with_200_is_error(self):
        client = IssueBadgeClient("k", "https://host")
        with patch(REQUEST, return_value=_resp(200, {"success": False, "message": "nope"})):
            with pytest.raises(ApiError, match="nope"):
                client.request("GET", "/badge/getall")

    def test_401_without_body_has_helpful_message(self):
        client = IssueBadgeClient("k", "https://host")
        with patch(REQUEST, return_value=_resp(401, content=b"")):
            with pytest.raises(ApiError, match="ISSUEBADGE_API_KEY"):
                client.request("GET", "/badge/getall")

    def test_html_error_page_is_not_echoed(self):
        client = IssueBadgeClient("k", "https://host")
        html = b"<!DOCTYPE html><html><head><title>Server Error</title></head><body>x</body></html>"
        with patch(REQUEST, return_value=_resp(500, content=html, content_type="text/html")):
            with pytest.raises(ApiError) as exc:
                client.request("GET", "/badge/x")
        assert str(exc.value) == "HTTP 500"
        assert exc.value.status == 500

    def test_raw_returns_bytes(self):
        client = IssueBadgeClient("k", "https://host")
        with patch(REQUEST, return_value=_resp(200, content=b"%PDF-1.4", content_type="application/pdf")) as m:
            out = client.request("POST", "/certificate/generate", json={"issued_badge_uuid": "x"}, raw=True)
        assert out == b"%PDF-1.4"
        assert _call(m)[2]["headers"]["Accept"] == "*/*"

    def test_raw_error_body_is_parsed(self):
        client = IssueBadgeClient("k", "https://host")
        with patch(REQUEST, return_value=_resp(404, {"success": False, "message": "No certificate design found"})):
            with pytest.raises(ApiError, match="No certificate design"):
                client.request("POST", "/certificate/generate", json={}, raw=True)

    def test_connection_error_is_api_error(self):
        client = IssueBadgeClient("k", "https://host")
        with patch(REQUEST, side_effect=backend.requests.ConnectionError("refused")):
            with pytest.raises(ApiError, match="Could not reach"):
                client.request("GET", "/badge/getall")

    def test_check_connectivity_ok(self):
        payload = {"success": True, "message": "API key is valid", "token_type": "Sanctum", "user": {"email": "a@b.c"}}
        with patch(REQUEST, return_value=_resp(200, payload)) as m:
            out = check_connectivity()
        assert out["ok"] is True
        assert out["token_type"] == "Sanctum"
        assert _call(m)[1].endswith("/api/v1/validate-key")

    def test_check_connectivity_bad_key(self):
        with patch(REQUEST, return_value=_resp(401, {"success": False, "message": "Invalid API key"})):
            out = check_connectivity()
        assert out["ok"] is False
        assert "Invalid API key" in out["message"]

    def test_check_connectivity_without_key(self, monkeypatch):
        monkeypatch.delenv("ISSUEBADGE_API_KEY")
        out = check_connectivity()
        assert out["ok"] is False
        assert "ISSUEBADGE_API_KEY" in out["message"]


# ---------------------------------------------------------------------------
# CLI help
# ---------------------------------------------------------------------------

class TestCLIHelp:
    @pytest.mark.parametrize(
        "args",
        [
            [], ["server"], ["badge"], ["issue"], ["certificate"], ["qrcode"], ["organization"],
            ["issue", "create"], ["issue", "bulk"], ["qrcode", "create"], ["certificate", "download"],
        ],
    )
    def test_help_exits_zero(self, runner, args):
        result = runner.invoke(cli, args + ["--help"])
        assert result.exit_code == 0, result.output

    def test_root_help_mentions_issuebadge(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert "IssueBadge" in result.output
        assert "--json" in result.output

    def test_version(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output


# ---------------------------------------------------------------------------
# server
# ---------------------------------------------------------------------------

class TestServer:
    def test_status_ok_json(self, runner):
        with patch(REQUEST, return_value=_resp(200, {"success": True, "message": "API key is valid"})):
            result = runner.invoke(cli, ["--json", "server", "status"])
        assert result.exit_code == 0
        assert json.loads(result.output)["ok"] is True

    def test_status_failure_exits_one(self, runner):
        with patch(REQUEST, return_value=_resp(401, {"success": False, "message": "Invalid API key"})):
            result = runner.invoke(cli, ["server", "status"])
        assert result.exit_code == 1
        assert "[ERROR]" in result.output


# ---------------------------------------------------------------------------
# badge
# ---------------------------------------------------------------------------

class TestBadgeCLI:
    def test_list_json(self, runner):
        payload = {"success": True, "data": [{"id": "b1", "name": "Cert", "description": "d", "organization_name": "Org"}]}
        with patch(REQUEST, return_value=_resp(200, payload)) as m:
            result = runner.invoke(cli, ["--json", "badge", "list"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["data"][0]["id"] == "b1"
        assert _call(m)[0] == "GET"
        assert _call(m)[1].endswith("/badge/getall")

    def test_list_pretty_table(self, runner):
        payload = {"success": True, "data": [{"id": "b1", "name": "Cert", "description": "d", "organization_name": "Org"}]}
        with patch(REQUEST, return_value=_resp(200, payload)):
            result = runner.invoke(cli, ["badge", "list"])
        assert result.exit_code == 0
        assert "b1" in result.output and "Cert" in result.output

    def test_show(self, runner):
        with patch(REQUEST, return_value=_resp(200, {"success": True, "data": {"id": "b1", "skills": ["a"]}})) as m:
            result = runner.invoke(cli, ["--json", "badge", "show", "b1"])
        assert result.exit_code == 0
        assert _call(m)[1].endswith("/badge/b1")

    def test_create_uploads_multipart(self, runner, tmp_path):
        logo = tmp_path / "logo.png"
        logo.write_bytes(b"\x89PNG")
        with patch(REQUEST, return_value=_resp(202, {"success": True, "badgeId": "b9"})) as m:
            result = runner.invoke(
                cli, ["--json", "badge", "create", "--name", "N", "--description", "D", "--logo", str(logo)]
            )
        assert result.exit_code == 0, result.output
        method, url, kwargs = _call(m)
        assert method == "POST" and url.endswith("/badge/create")
        assert kwargs["data"] == {"name": "N", "description": "D"}
        assert "badge_logo" in kwargs["files"]
        assert kwargs["json"] is None

    def test_create_missing_logo_rejected(self, runner):
        result = runner.invoke(cli, ["badge", "create", "--name", "N", "--description", "D", "--logo", "/nope.png"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# issue
# ---------------------------------------------------------------------------

class TestIssueCLI:
    def test_create_sends_compact_body_with_metadata(self, runner):
        payload = {"success": True, "IssueId": "i1", "publicUrl": "https://x/issue/view/i1"}
        with patch(REQUEST, return_value=_resp(202, payload)) as m:
            result = runner.invoke(
                cli,
                ["--json", "issue", "create", "--badge-id", "b1", "--name", "Ada", "--email", "ada@x.io",
                 "--meta", "score=95", "--meta", "course=CS101", "--expire-date", "2027-01-01"],
            )
        assert result.exit_code == 0, result.output
        method, url, kwargs = _call(m)
        assert method == "POST" and url.endswith("/issue/create")
        assert kwargs["json"] == {
            "badge_id": "b1", "name": "Ada", "email": "ada@x.io",
            "expire_date": "2027-01-01", "metadata": {"score": "95", "course": "CS101"},
        }
        assert json.loads(result.output)["IssueId"] == "i1"

    def test_create_bad_meta_rejected(self, runner):
        result = runner.invoke(cli, ["issue", "create", "--badge-id", "b1", "--name", "Ada", "--meta", "novalue"])
        assert result.exit_code != 0
        assert "key=value" in result.output

    def test_create_requires_badge_and_name(self, runner):
        result = runner.invoke(cli, ["issue", "create", "--name", "Ada"])
        assert result.exit_code != 0

    def test_list_forwards_filters(self, runner):
        payload = {"success": True, "data": [], "pagination": {"current_page": 2, "per_page": 5, "total": 0, "total_pages": 0}}
        with patch(REQUEST, return_value=_resp(200, payload)) as m:
            result = runner.invoke(cli, ["--json", "issue", "list", "--badge-id", "b1", "--email", "ada", "--page", "2", "--per-page", "5"])
        assert result.exit_code == 0
        assert _call(m)[2]["params"] == {"badge_id": "b1", "recipient_email": "ada", "page": 2, "per_page": 5}

    def test_list_per_page_capped(self, runner):
        result = runner.invoke(cli, ["issue", "list", "--per-page", "500"])
        assert result.exit_code != 0

    def test_show_and_history_routes(self, runner):
        with patch(REQUEST, return_value=_resp(200, {"success": True, "data": {"issue_id": "i1"}})) as m:
            assert runner.invoke(cli, ["--json", "issue", "show", "i1"]).exit_code == 0
            assert _call(m)[1].endswith("/issue/get/i1")
            assert runner.invoke(cli, ["--json", "issue", "history", "i1"]).exit_code == 0
            assert _call(m)[1].endswith("/issue/i1/history")

    def test_revoke(self, runner):
        with patch(REQUEST, return_value=_resp(200, {"success": True, "data": {"issue_id": "i1"}})) as m:
            result = runner.invoke(cli, ["--json", "issue", "revoke", "i1", "--reason", "Expired", "--comments", "c"])
        assert result.exit_code == 0
        method, url, kwargs = _call(m)
        assert method == "POST" and url.endswith("/issue/revoke")
        assert kwargs["json"] == {"issue_id": "i1", "reason": "Expired", "comments": "c"}

    def test_revoke_conflict_exit_one_json(self, runner):
        with patch(REQUEST, return_value=_resp(409, {"success": False, "message": "This assertion has already been revoked"})):
            result = runner.invoke(cli, ["--json", "issue", "revoke", "i1"])
        assert result.exit_code == 1
        err = json.loads(result.output)
        assert err["status"] == 409 and "already been revoked" in err["error"]

    def test_update_reinstate(self, runner):
        with patch(REQUEST, return_value=_resp(200, {"success": True, "data": {}})) as m:
            result = runner.invoke(cli, ["--json", "issue", "update", "i1", "--reinstate", "--memo", "back"])
        assert result.exit_code == 0
        method, url, kwargs = _call(m)
        assert method == "PATCH" and url.endswith("/issue/i1")
        assert kwargs["json"] == {"memo": "back", "reinstate": True}

    def test_update_without_fields_fails_locally(self, runner):
        with patch(REQUEST) as m:
            result = runner.invoke(cli, ["issue", "update", "i1"])
        assert result.exit_code == 1
        assert "Nothing to update" in result.output
        m.assert_not_called()


class TestBulkIssue:
    def _csv(self, tmp_path, text):
        p = tmp_path / "r.csv"
        p.write_text(text, encoding="utf-8")
        return str(p)

    def test_read_csv_requires_name(self, tmp_path):
        with pytest.raises(RuntimeError, match="'name' column"):
            issues_core.read_recipients_csv(self._csv(tmp_path, "email\nx@y.z\n"))

    def test_read_csv_empty(self, tmp_path):
        with pytest.raises(RuntimeError, match="no recipient rows"):
            issues_core.read_recipients_csv(self._csv(tmp_path, "name,email\n"))

    def test_bulk_issues_each_row_with_metadata(self, runner, tmp_path):
        path = self._csv(tmp_path, "name,email,score\nAda,ada@x.io,95\nAlan,,88\n")
        ok = _resp(202, {"success": True, "IssueId": "i1", "publicUrl": "u"})
        with patch(REQUEST, return_value=ok) as m:
            result = runner.invoke(cli, ["--json", "issue", "bulk", "--badge-id", "b1", "--csv", path, "--idempotency-prefix", "run7"])
        assert result.exit_code == 0, result.output
        assert m.call_count == 2
        first = m.call_args_list[0].kwargs["json"]
        second = m.call_args_list[1].kwargs["json"]
        assert first == {"badge_id": "b1", "name": "Ada", "email": "ada@x.io", "idempotency_key": "run7-1", "metadata": {"score": "95"}}
        assert second == {"badge_id": "b1", "name": "Alan", "idempotency_key": "run7-2", "metadata": {"score": "88"}}
        summary = json.loads(result.output)
        assert summary["issued"] == 2 and summary["failed"] == 0 and summary["ok"] is True

    def test_bulk_continues_after_failure_and_exits_one(self, runner, tmp_path):
        path = self._csv(tmp_path, "name,email\nAda,ada@x.io\n,none@x.io\nAlan,alan@x.io\n")
        ok = _resp(202, {"success": True, "IssueId": "i1", "publicUrl": "u"})
        with patch(REQUEST, return_value=ok) as m:
            result = runner.invoke(cli, ["--json", "issue", "bulk", "--badge-id", "b1", "--csv", path])
        assert result.exit_code == 1
        assert m.call_count == 2  # the empty-name row is rejected before any request
        summary = json.loads(result.output)
        assert summary["issued"] == 2 and summary["failed"] == 1
        assert summary["results"][1]["ok"] is False and "name is empty" in summary["results"][1]["error"]
        assert "idempotency_key" not in m.call_args_list[0].kwargs["json"]

    def test_bulk_api_error_recorded_per_row(self, runner, tmp_path):
        path = self._csv(tmp_path, "name\nAda\n")
        with patch(REQUEST, return_value=_resp(422, {"success": False, "message": "Validation failed", "errors": {"badge_id": ["bad"]}})):
            result = runner.invoke(cli, ["--json", "issue", "bulk", "--badge-id", "b1", "--csv", path])
        assert result.exit_code == 1
        assert "badge_id: bad" in json.loads(result.output)["results"][0]["error"]


# ---------------------------------------------------------------------------
# certificate
# ---------------------------------------------------------------------------

class TestCertificateCLI:
    def test_download_writes_pdf(self, runner, tmp_path):
        out = tmp_path / "c.pdf"
        with patch(REQUEST, return_value=_resp(200, content=b"%PDF-1.4 x", content_type="application/pdf")) as m:
            result = runner.invoke(cli, ["--json", "certificate", "download", "i1", "--out", str(out)])
        assert result.exit_code == 0, result.output
        assert out.read_bytes() == b"%PDF-1.4 x"
        method, url, kwargs = _call(m)
        assert method == "POST" and url.endswith("/certificate/generate")
        assert kwargs["json"] == {"issued_badge_uuid": "i1"}
        assert json.loads(result.output)["bytes"] == 10

    def test_download_no_design_exit_one(self, runner, tmp_path):
        out = tmp_path / "c.pdf"
        with patch(REQUEST, return_value=_resp(404, {"success": False, "message": "No certificate design found for this badge"})):
            result = runner.invoke(cli, ["certificate", "download", "i1", "--out", str(out)])
        assert result.exit_code == 1
        assert not out.exists()

    def test_batch_merges(self, runner, tmp_path):
        out = tmp_path / "all.pdf"
        with patch(REQUEST, return_value=_resp(200, content=b"%PDF", content_type="application/pdf")) as m:
            result = runner.invoke(cli, ["--json", "certificate", "batch", "i1", "i2", "--out", str(out)])
        assert result.exit_code == 0, result.output
        assert _call(m)[1].endswith("/certificate/batch/generate")
        assert _call(m)[2]["json"] == {"issued_badge_uuids": ["i1", "i2"]}
        assert json.loads(result.output)["count"] == 2


# ---------------------------------------------------------------------------
# qrcode
# ---------------------------------------------------------------------------

class TestQrcodeCLI:
    def test_create(self, runner):
        payload = {"success": True, "data": {"code": "btools_qrcode_A", "image_base64": "x" * 500}}
        with patch(REQUEST, return_value=_resp(201, payload)) as m:
            result = runner.invoke(cli, ["--json", "qrcode", "create", "--name", "L", "--type", "url", "--data", "url=https://e.com/a=b"])
        assert result.exit_code == 0, result.output
        assert _call(m)[2]["json"] == {"name": "L", "type": "url", "data": {"url": "https://e.com/a=b"}, "is_active": True}

    def test_create_pretty_truncates_base64(self, runner):
        payload = {"success": True, "data": {"code": "btools_qrcode_A", "image_base64": "x" * 500}}
        with patch(REQUEST, return_value=_resp(201, payload)):
            result = runner.invoke(cli, ["qrcode", "create", "--name", "L", "--type", "url", "--data", "url=https://e.com"])
        assert result.exit_code == 0
        assert "x" * 200 not in result.output

    def test_create_inactive_and_bad_type(self, runner):
        with patch(REQUEST, return_value=_resp(201, {"success": True, "data": {}})) as m:
            result = runner.invoke(cli, ["--json", "qrcode", "create", "--name", "L", "--type", "wifi", "--data", "ssid=Net", "--data", "password=p", "--inactive"])
        assert result.exit_code == 0
        assert _call(m)[2]["json"]["is_active"] is False
        assert runner.invoke(cli, ["qrcode", "create", "--name", "L", "--type", "bogus", "--data", "a=b"]).exit_code != 0

    def test_list_show_scans_delete_routes(self, runner):
        with patch(REQUEST, return_value=_resp(200, {"success": True, "data": []})) as m:
            assert runner.invoke(cli, ["--json", "qrcode", "list", "--type", "url", "--per-page", "5"]).exit_code == 0
            assert _call(m)[1].endswith("/qrcode") and _call(m)[2]["params"] == {"page": 1, "per_page": 5, "type": "url"}
            assert runner.invoke(cli, ["--json", "qrcode", "show", "c1"]).exit_code == 0
            assert _call(m)[1].endswith("/qrcode/c1")
            assert runner.invoke(cli, ["--json", "qrcode", "scans", "c1"]).exit_code == 0
            assert _call(m)[1].endswith("/qrcode/c1/scans")
            assert runner.invoke(cli, ["--json", "qrcode", "delete", "c1"]).exit_code == 0
            assert _call(m)[0] == "DELETE" and _call(m)[1].endswith("/qrcode/c1")

    def test_update_destination_and_disable(self, runner):
        with patch(REQUEST, return_value=_resp(200, {"success": True, "data": {}})) as m:
            result = runner.invoke(cli, ["--json", "qrcode", "update", "c1", "--data", "url=https://new", "--inactive"])
        assert result.exit_code == 0
        assert _call(m)[0] == "PATCH"
        assert _call(m)[2]["json"] == {"data": {"url": "https://new"}, "is_active": False}

    def test_update_nothing_fails_locally(self, runner):
        with patch(REQUEST) as m:
            result = runner.invoke(cli, ["qrcode", "update", "c1"])
        assert result.exit_code == 1 and "Nothing to update" in result.output
        m.assert_not_called()

    def test_image_writes_file(self, runner, tmp_path):
        out = tmp_path / "q.svg"
        with patch(REQUEST, return_value=_resp(200, content=b"<svg/>", content_type="image/svg+xml")) as m:
            result = runner.invoke(cli, ["--json", "qrcode", "image", "c1", "--out", str(out), "--size", "300", "--format", "svg"])
        assert result.exit_code == 0, result.output
        assert out.read_bytes() == b"<svg/>"
        assert _call(m)[2]["params"] == {"size": 300, "format": "svg"}

    def test_image_size_range(self, runner, tmp_path):
        assert runner.invoke(cli, ["qrcode", "image", "c1", "--out", str(tmp_path / "q.png"), "--size", "5000"]).exit_code != 0


# ---------------------------------------------------------------------------
# organization
# ---------------------------------------------------------------------------

class TestOrganizationCLI:
    def test_list_uses_post(self, runner):
        with patch(REQUEST, return_value=_resp(200, {"success": True, "data": [{"id": "o1", "name": "Org"}]})) as m:
            result = runner.invoke(cli, ["--json", "organization", "list"])
        assert result.exit_code == 0
        assert _call(m)[0] == "POST" and _call(m)[1].endswith("/organization/getall")

    def test_create(self, runner):
        with patch(REQUEST, return_value=_resp(202, {"success": True, "organizationId": "o2"})) as m:
            result = runner.invoke(cli, ["--json", "organization", "create", "--name", "Org", "--description", "D"])
        assert result.exit_code == 0
        assert _call(m)[2]["json"] == {"name": "Org", "description": "D"}


# ---------------------------------------------------------------------------
# Cross-cutting
# ---------------------------------------------------------------------------

class TestCrossCutting:
    def test_missing_key_exit_one_without_request(self, runner, monkeypatch):
        monkeypatch.delenv("ISSUEBADGE_API_KEY")
        with patch(REQUEST) as m:
            result = runner.invoke(cli, ["--json", "badge", "list"])
        assert result.exit_code == 1
        assert "ISSUEBADGE_API_KEY" in json.loads(result.output)["error"]
        m.assert_not_called()

    def test_base_url_flag(self, runner):
        with patch(REQUEST, return_value=_resp(200, {"success": True, "data": []})) as m:
            result = runner.invoke(cli, ["--base-url", "http://localhost:8000/", "badge", "list"])
        assert result.exit_code == 0
        assert _call(m)[1] == "http://localhost:8000/api/v1/badge/getall"

    def test_pretty_error_goes_to_stderr(self, runner):
        with patch(REQUEST, return_value=_resp(404, {"success": False, "message": "Badge not found"})):
            result = runner.invoke(cli, ["badge", "show", "nope"])
        assert result.exit_code == 1
        assert "Error: Badge not found" in result.output
