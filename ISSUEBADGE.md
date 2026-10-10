# ISSUEBADGE — Architecture & Design

## Overview

`cli-anything-issuebadge` is a CLI harness for [IssueBadge](https://issuebadge.com),
a platform for issuing digital certificates, badges and dynamic QR codes. The harness
exposes the IssueBadge REST API to AI coding agents (Claude Code, Codex, OpenCode, …)
as a structured command-line interface with JSON output.

## Backend

IssueBadge is a hosted web service with a bearer-token REST API under `/api/v1`.
There is no local process to launch: the harness sends HTTPS requests with
`requests`. Authentication comes from `ISSUEBADGE_API_KEY`; the host can be
overridden with `ISSUEBADGE_BASE_URL` or `--base-url` (default `https://app.issuebadge.com`).

The harness deliberately does not depend on the `digitalbadge` Python SDK: the SDK
covers only badge creation and issuance, while the CLI also needs revoke, reinstate,
history, certificates and QR codes.

## Command Hierarchy

```
cli-anything-issuebadge [--json] [--base-url URL]
├── server       status
├── badge        list | show <id> | create --name --description --logo
├── issue        create | bulk --csv | list | show <id> | history <id> | revoke <id> | update <id>
├── certificate  download <issue-id> --out | batch <issue-id>... --out
├── qrcode       list | create | show <code> | image <code> --out | update <code> | scans <code> | delete <code>
└── organization list | create --name
```

## Endpoint Mapping

| Command | Method | Endpoint |
|---|---|---|
| `server status` | POST | `/validate-key` |
| `badge list` / `show` / `create` | GET / GET / POST (multipart) | `/badge/getall`, `/badge/{id}`, `/badge/create` |
| `issue create` | POST | `/issue/create` |
| `issue bulk` | POST ×N | `/issue/create` (one request per CSV row) |
| `issue list` / `show` / `history` | GET | `/issue/get`, `/issue/get/{id}`, `/issue/{id}/history` |
| `issue revoke` | POST | `/issue/revoke` |
| `issue update` | PATCH | `/issue/{id}` |
| `certificate download` / `batch` | POST | `/certificate/generate`, `/certificate/batch/generate` (PDF bytes) |
| `qrcode *` | GET/POST/PATCH/DELETE | `/qrcode`, `/qrcode/create`, `/qrcode/{code}`, `/qrcode/{code}/image`, `/qrcode/{code}/scans` |
| `organization list` / `create` | POST | `/organization/getall`, `/organization/create` |

## Output Strategy

Human-readable output is the default: list responses render as aligned tables with
a fixed preferred column order, detail responses as `key: value` blocks with long
values truncated. `--json` prints the API response verbatim (indented), so agents
read exactly the documented payloads.

Errors are uniform. Any non-2xx response, `success: false` body or transport
failure becomes an `ApiError` carrying the HTTP status and the server's `errors`
map. In JSON mode the error is printed on stdout as `{"error", "status", "errors"?}`;
in text mode as `Error: …` on stderr. Exit code is always 1.

Binary endpoints (PDF, PNG, SVG) are requested with `raw=True`; the bytes are
written to `--out` and a small `{ok, path, bytes}` summary is printed.

## State Model

The harness is stateless. Every command performs one or more HTTP calls and exits;
the REPL simply re-dispatches lines through the same Click tree. Undo/redo is not
meaningful for a hosted API; reversible operations are modelled by the API itself
(`issue revoke` ↔ `issue update --reinstate`, `qrcode update --inactive` ↔ `--active`).

## Design Decisions

**Bulk issuance is client-side.** The API has no batch issue endpoint. `issue bulk`
loops over CSV rows, never aborts on a failed row, and reports every outcome so an
agent can retry only the failures. `--idempotency-prefix` derives `<prefix>-<row>`
keys, making a rerun of the same file a no-op on the server.

**Custom fields as `KEY=VALUE`.** Badge templates define arbitrary custom fields;
`--meta` (and extra CSV columns) map straight to the `metadata` object instead of
hard-coding field names.

**QR `--data` is type-agnostic.** The API validates `data` per `type`; the CLI
forwards whatever `--data` pairs are given and surfaces the server's validation
errors rather than duplicating the rules.

**Local guards before network.** `issue update` and `qrcode update` fail locally
when no field is given, and a missing API key fails before any request.

## File Layout

```
cli-anything-issuebadge/
├── setup.py
├── SKILL.md                         Canonical skill (copied into the package)
├── ISSUEBADGE.md                    (this file)
├── registry-entry.json              Entry for CLI-Anything's registry.json
└── cli_anything/issuebadge/
    ├── __init__.py
    ├── __main__.py
    ├── issuebadge_cli.py            Entry point, Click command tree, REPL
    ├── README.md                    Setup and usage guide (PyPI long description)
    ├── core/
    │   ├── badges.py                list_badges(), get_badge(), create_badge()
    │   ├── issues.py                issue_badge(), bulk_issue(), list/get/history/revoke/update
    │   ├── certificates.py          download_certificate(), download_batch()
    │   ├── qrcodes.py               QR CRUD, scans, image download
    │   └── organizations.py         list_organizations(), create_organization()
    ├── utils/
    │   ├── issuebadge_backend.py    IssueBadgeClient, ApiError, check_connectivity()
    │   └── repl_skin.py             Shared REPL terminal UI (unmodified cli-anything copy)
    ├── skills/
    │   └── SKILL.md                 Packaged copy for runtime discovery
    └── tests/
        ├── TEST.md
        ├── test_core.py             Unit tests (HTTP mocked, no key needed)
        └── test_full_e2e.py         Real API tests (ISSUEBADGE_API_KEY required)
```
