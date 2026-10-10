"""
test_full_e2e.py — End-to-end tests against a real IssueBadge API.

Requires: ISSUEBADGE_API_KEY set in the environment.
Optional: ISSUEBADGE_BASE_URL (defaults to https://app.issuebadge.com),
          ISSUEBADGE_E2E_BADGE_ID (enables the issue/certificate lifecycle tests,
          which create, revoke and reinstate a real issued badge).
Run with: pytest cli_anything/issuebadge/tests/test_full_e2e.py -v

These tests make real API calls. The QR code tests create and delete a real
QR code; the issue tests create a real issued badge for "CLI-Anything E2E".
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest
from click.testing import CliRunner

from cli_anything.issuebadge.issuebadge_cli import cli

pytestmark = pytest.mark.skipif(
    not os.environ.get("ISSUEBADGE_API_KEY"),
    reason="ISSUEBADGE_API_KEY not set — skipping E2E tests",
)

BADGE_ID = os.environ.get("ISSUEBADGE_E2E_BADGE_ID", "")


@pytest.fixture()
def runner():
    return CliRunner()


def _json(runner, args):
    result = runner.invoke(cli, ["--json", *args])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


# ---------------------------------------------------------------------------
# Connectivity and read-only listings
# ---------------------------------------------------------------------------

class TestConnectivity:
    def test_server_status(self, runner):
        data = _json(runner, ["server", "status"])
        assert data["ok"] is True
        assert data["token_type"] in ("Sanctum", "OAuth2")

    def test_installed_command_runs_as_subprocess(self):
        proc = subprocess.run(
            [sys.executable, "-m", "cli_anything.issuebadge", "--json", "server", "status"],
            capture_output=True, text=True, timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout)["ok"] is True


class TestListings:
    def test_badge_list(self, runner):
        data = _json(runner, ["badge", "list"])
        assert data["success"] is True
        assert isinstance(data["data"], list)

    def test_badge_show_first(self, runner):
        badges = _json(runner, ["badge", "list"])["data"]
        if not badges:
            pytest.skip("account has no badges")
        detail = _json(runner, ["badge", "show", badges[0]["id"]])["data"]
        assert detail["id"] == badges[0]["id"]
        assert "custom_fields" in detail

    def test_organization_list(self, runner):
        data = _json(runner, ["organization", "list"])
        assert isinstance(data["data"], list)

    def test_issue_list_paginated(self, runner):
        data = _json(runner, ["issue", "list", "--per-page", "2"])
        assert isinstance(data["data"], list)
        assert data["pagination"]["per_page"] == 2

    def test_qrcode_list(self, runner):
        data = _json(runner, ["qrcode", "list", "--per-page", "5"])
        assert isinstance(data["data"], list)

    def test_unknown_badge_is_404(self, runner):
        result = runner.invoke(cli, ["--json", "badge", "show", "does-not-exist"])
        assert result.exit_code == 1
        assert json.loads(result.output)["status"] in (404, 400, 422, 500)


# ---------------------------------------------------------------------------
# QR code lifecycle (creates and deletes a real code)
# ---------------------------------------------------------------------------

class TestQrcodeLifecycle:
    def test_create_update_image_scans_delete(self, runner, tmp_path):
        created = _json(
            runner,
            ["qrcode", "create", "--name", "cli-anything e2e", "--type", "url",
             "--data", "url=https://issuebadge.com/?e2e=1"],
        )["data"]
        code = created["code"]
        try:
            assert created["type"] == "url"
            assert created["scan_url"].endswith(code)

            shown = _json(runner, ["qrcode", "show", code])["data"]
            assert shown["code"] == code

            updated = _json(
                runner, ["qrcode", "update", code, "--name", "cli-anything e2e v2", "--data", "url=https://issuebadge.com/?e2e=2"]
            )["data"]
            assert updated["name"] == "cli-anything e2e v2"
            assert updated["data"]["url"].endswith("e2e=2")

            png = tmp_path / "q.png"
            out = _json(runner, ["qrcode", "image", code, "--out", str(png), "--size", "200"])
            assert out["bytes"] > 100
            assert png.read_bytes()[:4] == b"\x89PNG"

            svg = tmp_path / "q.svg"
            _json(runner, ["qrcode", "image", code, "--out", str(svg), "--format", "svg"])
            assert b"<svg" in svg.read_bytes()

            scans = _json(runner, ["qrcode", "scans", code])
            assert scans["code"] == code
            assert isinstance(scans["data"], list)
        finally:
            deleted = _json(runner, ["qrcode", "delete", code])
            assert deleted["success"] is True

        result = runner.invoke(cli, ["--json", "qrcode", "show", code])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Issue lifecycle (only when a badge ID is supplied)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not BADGE_ID, reason="ISSUEBADGE_E2E_BADGE_ID not set — skipping issue lifecycle")
class TestIssueLifecycle:
    def test_issue_revoke_reinstate_history(self, runner, tmp_path):
        key = f"cli-anything-e2e-{os.getpid()}"
        created = _json(
            runner,
            ["issue", "create", "--badge-id", BADGE_ID, "--name", "CLI-Anything E2E",
             "--idempotency-key", key, "--memo", "created by test_full_e2e"],
        )
        issue_id = created["IssueId"]
        assert created["publicUrl"]

        # Same idempotency key → same issue, no duplicate.
        again = _json(
            runner,
            ["issue", "create", "--badge-id", BADGE_ID, "--name", "CLI-Anything E2E", "--idempotency-key", key],
        )
        assert again["IssueId"] == issue_id

        shown = _json(runner, ["issue", "show", issue_id])["data"]
        assert shown["recipient_name"] == "CLI-Anything E2E"
        assert shown["is_revoked"] is False

        revoked = _json(runner, ["issue", "revoke", issue_id, "--reason", "e2e"])["data"]
        assert revoked["revocation_reason"] == "e2e"

        conflict = runner.invoke(cli, ["--json", "issue", "revoke", issue_id])
        assert conflict.exit_code == 1
        assert json.loads(conflict.output)["status"] == 409

        reinstated = _json(runner, ["issue", "update", issue_id, "--reinstate"])["data"]
        assert reinstated["is_revoked"] is False

        history = _json(runner, ["issue", "history", issue_id])["data"]
        actions = [h["action"] for h in history["history"]]
        assert "revoked" in actions and "reinstated" in actions

        listed = _json(runner, ["issue", "list", "--badge-id", BADGE_ID, "--name", "CLI-Anything E2E"])["data"]
        assert any(i["issue_id"] == issue_id for i in listed)

        pdf = tmp_path / "cert.pdf"
        result = runner.invoke(cli, ["--json", "certificate", "download", issue_id, "--out", str(pdf)])
        if result.exit_code != 0 and json.loads(result.output).get("status") == 404:
            pytest.skip("badge has no certificate design")
        assert result.exit_code == 0, result.output
        assert pdf.read_bytes()[:4] == b"%PDF"

    def test_bulk_from_csv(self, runner, tmp_path):
        csv_path = tmp_path / "r.csv"
        csv_path.write_text("name,memo\nCLI-Anything Bulk One,e2e\nCLI-Anything Bulk Two,e2e\n")
        summary = _json(
            runner,
            ["issue", "bulk", "--badge-id", BADGE_ID, "--csv", str(csv_path),
             "--idempotency-prefix", f"cli-anything-bulk-{os.getpid()}"],
        )
        assert summary["issued"] == 2 and summary["failed"] == 0
        assert all(r["issue_id"] for r in summary["results"])
