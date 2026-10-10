"""issuebadge_cli.py — CLI harness for IssueBadge.

Agent-native command-line interface for the IssueBadge API
(digital certificates, badges and dynamic QR codes).

Usage (non-interactive):
    cli-anything-issuebadge server status
    cli-anything-issuebadge --json badge list
    cli-anything-issuebadge --json issue create --badge-id <id> --name "Ada Lovelace" --email ada@example.com
    cli-anything-issuebadge --json issue bulk --badge-id <id> --csv recipients.csv
    cli-anything-issuebadge certificate download <issue-id> --out certificate.pdf
    cli-anything-issuebadge --json qrcode create --name "Launch" --type url --data url=https://example.com

Usage (interactive REPL):
    cli-anything-issuebadge
"""

from __future__ import annotations

import functools
import json
import sys
from typing import Any, Callable

import click

from cli_anything.issuebadge.core import badges as badges_core
from cli_anything.issuebadge.core import certificates as certificates_core
from cli_anything.issuebadge.core import issues as issues_core
from cli_anything.issuebadge.core import organizations as organizations_core
from cli_anything.issuebadge.core import qrcodes as qrcodes_core
from cli_anything.issuebadge.utils.issuebadge_backend import (
    VERSION,
    ApiError,
    check_connectivity,
    get_client,
)

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

_json_output: bool = False
_base_url: str | None = None

# Preferred column order for human-readable tables.
_TABLE_COLUMNS = (
    "id", "code", "issue_id", "name", "recipient_name", "recipient_email", "badge_name",
    "organization_name", "type", "scan_count", "issue_date", "expire_date", "is_revoked",
    "is_active", "scanned_at", "ip_address", "action", "changed_by", "created_at",
)
_MAX_CELL = 40
_MAX_VALUE = 120


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _out(data: Any) -> None:
    """Emit output in JSON or human-readable form."""
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        _pretty(data)


def _pretty(data: Any) -> None:
    if isinstance(data, dict):
        rows = data.get("data")
        if isinstance(rows, list):
            _print_table(rows)
            pagination = data.get("pagination")
            if pagination:
                total_pages = pagination.get("total_pages") or pagination.get("last_page")
                click.echo(
                    f"Page {pagination.get('current_page')} of {total_pages} · {pagination.get('total')} total"
                )
            return
        if isinstance(rows, dict):
            _print_kv(rows)
            return
        if "ok" in data and "results" not in data:
            status = "OK" if data["ok"] else "ERROR"
            click.echo(f"[{status}] {data.get('message', '')}".rstrip())
            _print_kv({k: v for k, v in data.items() if k not in ("ok", "message")})
            return
        if isinstance(data.get("results"), list):
            _print_kv({k: v for k, v in data.items() if k != "results"})
            _print_table(data["results"])
            return
        _print_kv(data)
    elif isinstance(data, list):
        _print_table(data)
    else:
        click.echo(str(data))


def _cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, default=str)
    text = str(value) if value is not None else ""
    return text if len(text) <= _MAX_CELL else text[: _MAX_CELL - 1] + "…"


def _print_table(rows: list[Any]) -> None:
    if not rows:
        click.echo("No results.")
        return
    if not all(isinstance(r, dict) for r in rows):
        for r in rows:
            click.echo(str(r))
        return
    keys = list(rows[0].keys())
    columns = [k for k in _TABLE_COLUMNS if k in keys] or keys[:6]
    widths = {c: max(len(c), *(len(_cell(r.get(c))) for r in rows)) for c in columns}
    click.echo("  ".join(c.ljust(widths[c]) for c in columns))
    click.echo("  ".join("─" * widths[c] for c in columns))
    for r in rows:
        click.echo("  ".join(_cell(r.get(c)).ljust(widths[c]) for c in columns))


def _print_kv(data: dict[str, Any], indent: int = 0) -> None:
    pad = " " * indent
    for key, value in data.items():
        if isinstance(value, dict) and value:
            click.echo(f"{pad}{key}:")
            _print_kv(value, indent + 2)
        elif isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
            click.echo(f"{pad}{key}:")
            _print_table(value)
        else:
            text = json.dumps(value, default=str) if isinstance(value, (dict, list)) else str(value)
            if len(text) > _MAX_VALUE:
                text = text[: _MAX_VALUE - 1] + "…"
            click.echo(f"{pad}{key}: {text}")


def _err(error: str | dict[str, Any]) -> None:
    if _json_output:
        payload = error if isinstance(error, dict) else {"error": error}
        click.echo(json.dumps(payload, indent=2, default=str))
    else:
        message = error["error"] if isinstance(error, dict) else error
        click.echo(f"Error: {message}", err=True)


def _handle_errors(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Catch backend errors and emit a consistent error payload with exit 1."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except ApiError as exc:
            _err(exc.to_dict())
            sys.exit(1)
        except RuntimeError as exc:
            _err(str(exc))
            sys.exit(1)
        except OSError as exc:
            _err(f"File error: {exc}")
            sys.exit(1)

    return wrapper


def _parse_kv(pairs: tuple[str, ...], flag: str) -> dict[str, str]:
    """Turn repeated ``key=value`` options into a dict."""
    out: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise click.BadParameter(f"expected key=value, got {pair!r}", param_hint=flag)
        key, _, value = pair.partition("=")
        out[key.strip()] = value
    return out


def _client():
    return get_client(_base_url)


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Emit machine-readable JSON output.")
@click.option("--base-url", default=None, metavar="URL",
              help="API host (default: $ISSUEBADGE_BASE_URL or https://app.issuebadge.com).")
@click.version_option(VERSION, prog_name="cli-anything-issuebadge")
@click.pass_context
def cli(ctx: click.Context, use_json: bool, base_url: str | None) -> None:
    """CLI harness for IssueBadge — digital certificates, badges and QR codes.

    Run without a subcommand to enter the interactive REPL.
    Set ISSUEBADGE_API_KEY in your environment before use.
    """
    global _json_output, _base_url
    _json_output = use_json
    _base_url = base_url
    ctx.ensure_object(dict)

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ---------------------------------------------------------------------------
# server
# ---------------------------------------------------------------------------

@cli.group("server")
def server_group() -> None:
    """API connectivity commands."""


@server_group.command("status")
@_handle_errors
def server_status() -> None:
    """Check that the IssueBadge API accepts your API key."""
    result = check_connectivity(_base_url)
    _out(result)
    if not result.get("ok"):
        sys.exit(1)


# ---------------------------------------------------------------------------
# badge
# ---------------------------------------------------------------------------

@cli.group("badge")
def badge_group() -> None:
    """Badge templates (the design a certificate is issued from)."""


@badge_group.command("list")
@_handle_errors
def badge_list() -> None:
    """List all badge templates in the account."""
    _out(badges_core.list_badges(_client()))


@badge_group.command("show")
@click.argument("badge_id")
@_handle_errors
def badge_show(badge_id: str) -> None:
    """Show one badge template, including its custom fields and expiration rule."""
    _out(badges_core.get_badge(_client(), badge_id))


@badge_group.command("create")
@click.option("--name", required=True, help="Badge name.")
@click.option("--description", required=True, help="Badge description.")
@click.option("--logo", "logo_path", required=True, type=click.Path(exists=True, dir_okay=False),
              help="Badge image file (jpeg, png, jpg, gif, svg).")
@_handle_errors
def badge_create(name: str, description: str, logo_path: str) -> None:
    """Create a badge template from a name, description and logo image."""
    _out(badges_core.create_badge(_client(), name, description, logo_path))


# ---------------------------------------------------------------------------
# issue
# ---------------------------------------------------------------------------

@cli.group("issue")
def issue_group() -> None:
    """Issued badges and certificates."""


@issue_group.command("create")
@click.option("--badge-id", required=True, help="Badge template ID (from `badge list`).")
@click.option("--name", required=True, help="Recipient full name.")
@click.option("--email", default=None, help="Recipient email (the certificate is emailed when set).")
@click.option("--idempotency-key", default=None,
              help="Unique key; repeating it returns the existing issue instead of creating a duplicate.")
@click.option("--issue-date", default=None, metavar="YYYY-MM-DD", help="Issue date (default: today).")
@click.option("--expire-date", default=None, metavar="YYYY-MM-DD", help="Expiration date.")
@click.option("--memo", default=None, help="Internal memo.")
@click.option("--meta", multiple=True, metavar="KEY=VALUE",
              help="Custom field value (repeatable), e.g. --meta score=95.")
@_handle_errors
def issue_create(
    badge_id: str,
    name: str,
    email: str | None,
    idempotency_key: str | None,
    issue_date: str | None,
    expire_date: str | None,
    memo: str | None,
    meta: tuple[str, ...],
) -> None:
    """Issue a badge/certificate to one recipient."""
    _out(
        issues_core.issue_badge(
            _client(),
            badge_id,
            name=name,
            email=email,
            idempotency_key=idempotency_key,
            issue_date=issue_date,
            expire_date=expire_date,
            memo=memo,
            metadata=_parse_kv(meta, "--meta") or None,
        )
    )


@issue_group.command("bulk")
@click.option("--badge-id", required=True, help="Badge template ID.")
@click.option("--csv", "csv_path", required=True, type=click.Path(exists=True, dir_okay=False),
              help="CSV with a header row: name[,email,issue_date,expire_date,memo,idempotency_key,...custom fields].")
@click.option("--idempotency-prefix", default=None,
              help="Derive each row's idempotency key as <prefix>-<row number>, so a rerun never duplicates.")
@_handle_errors
def issue_bulk(badge_id: str, csv_path: str, idempotency_prefix: str | None) -> None:
    """Issue one badge per CSV row. Reports every row; exits 1 if any row failed."""
    rows = issues_core.read_recipients_csv(csv_path)
    result = issues_core.bulk_issue(_client(), badge_id, rows, idempotency_prefix=idempotency_prefix)
    _out(result)
    if not result["ok"]:
        sys.exit(1)


@issue_group.command("list")
@click.option("--badge-id", default=None, help="Filter by badge template ID.")
@click.option("--name", "recipient_name", default=None, help="Filter by recipient name (partial match).")
@click.option("--email", "recipient_email", default=None, help="Filter by recipient email (partial match).")
@click.option("--page", default=1, show_default=True, type=click.IntRange(1), help="Page number.")
@click.option("--per-page", default=10, show_default=True, type=click.IntRange(1, 100), help="Items per page.")
@_handle_errors
def issue_list(
    badge_id: str | None, recipient_name: str | None, recipient_email: str | None, page: int, per_page: int
) -> None:
    """List issued badges with optional filters and pagination."""
    _out(issues_core.list_issues(_client(), badge_id, recipient_name, recipient_email, page, per_page))


@issue_group.command("show")
@click.argument("issue_id")
@_handle_errors
def issue_show(issue_id: str) -> None:
    """Show one issued badge (recipient, dates, revocation state, public URL, metadata)."""
    _out(issues_core.get_issue(_client(), issue_id))


@issue_group.command("history")
@click.argument("issue_id")
@_handle_errors
def issue_history(issue_id: str) -> None:
    """Show the audit history (revocations, reinstatements, updates) of an issued badge."""
    _out(issues_core.get_history(_client(), issue_id))


@issue_group.command("revoke")
@click.argument("issue_id")
@click.option("--reason", default=None, help="Short reason (default: 'Revoked via API').")
@click.option("--comments", default=None, help="Additional comments (max 200 characters).")
@_handle_errors
def issue_revoke(issue_id: str, reason: str | None, comments: str | None) -> None:
    """Revoke an issued badge."""
    _out(issues_core.revoke_issue(_client(), issue_id, reason, comments))


@issue_group.command("update")
@click.argument("issue_id")
@click.option("--expire-date", default=None, metavar="YYYY-MM-DD", help="New expiration date.")
@click.option("--memo", default=None, help="New memo.")
@click.option("--reinstate", is_flag=True, help="Reinstate a revoked badge.")
@_handle_errors
def issue_update(issue_id: str, expire_date: str | None, memo: str | None, reinstate: bool) -> None:
    """Extend expiration, change the memo, or reinstate a revoked badge."""
    _out(issues_core.update_issue(_client(), issue_id, expire_date, memo, reinstate))


# ---------------------------------------------------------------------------
# certificate
# ---------------------------------------------------------------------------

@cli.group("certificate")
def certificate_group() -> None:
    """Rendered certificate PDFs."""


@certificate_group.command("download")
@click.argument("issue_id")
@click.option("--out", "out_path", required=True, type=click.Path(dir_okay=False), help="Where to save the PDF.")
@_handle_errors
def certificate_download(issue_id: str, out_path: str) -> None:
    """Render the certificate PDF for one issued badge and save it."""
    _out(certificates_core.download_certificate(_client(), issue_id, out_path))


@certificate_group.command("batch")
@click.argument("issue_ids", nargs=-1, required=True)
@click.option("--out", "out_path", required=True, type=click.Path(dir_okay=False),
              help="Where to save the merged PDF.")
@_handle_errors
def certificate_batch(issue_ids: tuple[str, ...], out_path: str) -> None:
    """Render several certificates into one merged PDF."""
    _out(certificates_core.download_batch(_client(), list(issue_ids), out_path))


# ---------------------------------------------------------------------------
# qrcode
# ---------------------------------------------------------------------------

_QR_TYPES = click.Choice(qrcodes_core.QR_TYPES, case_sensitive=False)


@cli.group("qrcode")
def qrcode_group() -> None:
    """Dynamic QR codes (editable destination, scan tracking)."""


@qrcode_group.command("list")
@click.option("--type", "qr_type", type=_QR_TYPES, default=None, help="Filter by QR type.")
@click.option("--page", default=1, show_default=True, type=click.IntRange(1), help="Page number.")
@click.option("--per-page", default=20, show_default=True, type=click.IntRange(1, 100), help="Items per page.")
@_handle_errors
def qrcode_list(qr_type: str | None, page: int, per_page: int) -> None:
    """List QR codes."""
    _out(qrcodes_core.list_qrcodes(_client(), qr_type, page, per_page))


@qrcode_group.command("create")
@click.option("--name", required=True, help="Label for the QR code.")
@click.option("--type", "qr_type", type=_QR_TYPES, required=True, help="QR type (url, text, email, wifi, vcard, ...).")
@click.option("--data", multiple=True, metavar="KEY=VALUE", required=True,
              help="Payload field for the type (repeatable), e.g. --data url=https://example.com.")
@click.option("--inactive", is_flag=True, help="Create the code disabled (scans return 404).")
@_handle_errors
def qrcode_create(name: str, qr_type: str, data: tuple[str, ...], inactive: bool) -> None:
    """Create a dynamic QR code."""
    payload = _parse_kv(data, "--data")
    _out(qrcodes_core.create_qrcode(_client(), name, qr_type.lower(), payload, is_active=not inactive))


@qrcode_group.command("show")
@click.argument("code")
@_handle_errors
def qrcode_show(code: str) -> None:
    """Show one QR code (destination, scan count, scan URL, image URL)."""
    _out(qrcodes_core.get_qrcode(_client(), code))


@qrcode_group.command("image")
@click.argument("code")
@click.option("--out", "out_path", required=True, type=click.Path(dir_okay=False), help="Where to save the image.")
@click.option("--size", default=500, show_default=True, type=click.IntRange(100, 2000), help="Pixels per side.")
@click.option("--format", "fmt", default="png", show_default=True,
              type=click.Choice(["png", "svg"], case_sensitive=False), help="Image format.")
@_handle_errors
def qrcode_image(code: str, out_path: str, size: int, fmt: str) -> None:
    """Download the QR image as PNG or SVG."""
    _out(qrcodes_core.download_image(_client(), code, out_path, size, fmt.lower()))


@qrcode_group.command("update")
@click.argument("code")
@click.option("--name", default=None, help="New label.")
@click.option("--data", multiple=True, metavar="KEY=VALUE", help="New payload field (repeatable).")
@click.option("--active/--inactive", "is_active", default=None, help="Enable or disable scans.")
@_handle_errors
def qrcode_update(code: str, name: str | None, data: tuple[str, ...], is_active: bool | None) -> None:
    """Change where a QR code points, rename it, or enable/disable it. The printed image stays valid."""
    _out(qrcodes_core.update_qrcode(_client(), code, name, _parse_kv(data, "--data") or None, is_active))


@qrcode_group.command("scans")
@click.argument("code")
@click.option("--page", default=1, show_default=True, type=click.IntRange(1), help="Page number.")
@click.option("--per-page", default=50, show_default=True, type=click.IntRange(1, 100), help="Items per page.")
@_handle_errors
def qrcode_scans(code: str, page: int, per_page: int) -> None:
    """List scan events for a QR code."""
    _out(qrcodes_core.list_scans(_client(), code, page, per_page))


@qrcode_group.command("delete")
@click.argument("code")
@_handle_errors
def qrcode_delete(code: str) -> None:
    """Delete a QR code permanently."""
    _out(qrcodes_core.delete_qrcode(_client(), code))


# ---------------------------------------------------------------------------
# organization
# ---------------------------------------------------------------------------

@cli.group("organization")
def organization_group() -> None:
    """Issuing organisations."""


@organization_group.command("list")
@_handle_errors
def organization_list() -> None:
    """List organisations in the account."""
    _out(organizations_core.list_organizations(_client()))


@organization_group.command("create")
@click.option("--name", required=True, help="Organisation name.")
@click.option("--description", default=None, help="Organisation description.")
@_handle_errors
def organization_create(name: str, description: str | None) -> None:
    """Create an organisation."""
    _out(organizations_core.create_organization(_client(), name, description))


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------

@cli.command("repl")
def repl() -> None:
    """Start the interactive REPL (default when no subcommand is given)."""
    import shlex

    from cli_anything.issuebadge.utils.repl_skin import ReplSkin

    skin = ReplSkin(software="issuebadge", version=VERSION)
    skin.print_banner()
    pt_session = skin.create_prompt_session()

    while True:
        try:
            line = skin.get_input(pt_session).strip()
        except (KeyboardInterrupt, EOFError):
            skin.print_goodbye()
            break

        if not line:
            continue
        if line.lower() in ("exit", "quit", "q"):
            skin.print_goodbye()
            break

        try:
            args = shlex.split(line)
            cli.main(args=args, standalone_mode=False)
        except SystemExit:
            pass
        except ValueError as exc:
            _err(f"Invalid input: {exc}")
        except Exception as exc:  # noqa: BLE001
            _err(str(exc))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    cli()


if __name__ == "__main__":
    main()
