---
name: "cli-anything-issuebadge"
description: >-
  Agent-native CLI for IssueBadge: issue, list, revoke and reinstate digital
  certificates and badges, download certificate PDFs, and manage dynamic QR codes.
---

# IssueBadge CLI Skill

## Identity
- **Name**: cli-anything-issuebadge
- **Version**: 1.0.0
- **Category**: web
- **Entry Point**: `cli-anything-issuebadge`

## What This CLI Does
Wraps the [IssueBadge](https://issuebadge.com) REST API so an agent can run a
credentialing workflow from the shell: pick a badge template, issue certificates
to one recipient or a whole CSV, revoke or reinstate them, pull the rendered PDF,
read the audit trail, and create trackable QR codes whose destination can be
changed after printing.

## Prerequisites
- Python >= 3.10
- An IssueBadge account and API key (app.issuebadge.com → Developer → API keys)
- `export ISSUEBADGE_API_KEY="your-api-key"`
- Optional: `export ISSUEBADGE_BASE_URL="https://app.issuebadge.com"` (self-hosted or staging hosts)

## Installation
```bash
pip install git+https://github.com/issuebadge2026/cli-anything-issuebadge
```

## Command Reference

### server status — Verify the API key
```bash
cli-anything-issuebadge server status
```

### badge — Badge templates
```bash
cli-anything-issuebadge badge list
cli-anything-issuebadge badge show <badge-id>          # custom fields, expiration rule, skills
cli-anything-issuebadge badge create --name "Course Completion" --description "..." --logo logo.png
```

### issue — Issued badges / certificates
```bash
cli-anything-issuebadge issue create --badge-id <id> --name "Ada Lovelace" [OPTIONS]

Options:
  --email EMAIL             Recipient email; the certificate is emailed when set
  --idempotency-key KEY     Repeating a key returns the existing issue (safe retries)
  --issue-date YYYY-MM-DD   Defaults to today
  --expire-date YYYY-MM-DD
  --memo TEXT
  --meta KEY=VALUE          Custom field value (repeatable)

cli-anything-issuebadge issue bulk --badge-id <id> --csv recipients.csv [--idempotency-prefix run-42]
cli-anything-issuebadge issue list [--badge-id ID] [--name TEXT] [--email TEXT] [--page N] [--per-page 1-100]
cli-anything-issuebadge issue show <issue-id>
cli-anything-issuebadge issue history <issue-id>
cli-anything-issuebadge issue revoke <issue-id> [--reason TEXT] [--comments TEXT]
cli-anything-issuebadge issue update <issue-id> [--expire-date YYYY-MM-DD] [--memo TEXT] [--reinstate]
```

CSV for `issue bulk`: header row with `name` (required) and optionally `email`,
`issue_date`, `expire_date`, `memo`, `idempotency_key`. Every other column is sent
as a custom field value. Rows are processed independently; the summary lists each
row's outcome and the command exits 1 if any row failed.

### certificate — Rendered PDFs
```bash
cli-anything-issuebadge certificate download <issue-id> --out certificate.pdf
cli-anything-issuebadge certificate batch <issue-id> <issue-id> ... --out all.pdf   # one merged PDF
```

### qrcode — Dynamic QR codes
```bash
cli-anything-issuebadge qrcode list [--type url] [--page N] [--per-page 1-100]
cli-anything-issuebadge qrcode create --name "Launch" --type url --data url=https://example.com [--inactive]
cli-anything-issuebadge qrcode show <code>
cli-anything-issuebadge qrcode image <code> --out qr.png [--size 100-2000] [--format png|svg]
cli-anything-issuebadge qrcode update <code> [--name TEXT] [--data KEY=VALUE ...] [--active|--inactive]
cli-anything-issuebadge qrcode scans <code> [--page N] [--per-page 1-100]
cli-anything-issuebadge qrcode delete <code>
```

Types and their `--data` keys: `url` (url), `text` (text), `email` (to, subject, body),
`phone` (phone), `sms` (phone, message), `wifi` (ssid, password, security),
`vcard` (name, organization, phone, email, website, address), `mecard` (name, phone,
email, memo), `maps` (latitude, longitude, name), `event` (title, location,
description, start, end), `paypal` (paypal_id, amount, currency), `facebook` (url),
`twitter` (username), `youtube` (url).

### organization — Issuing organisations
```bash
cli-anything-issuebadge organization list
cli-anything-issuebadge organization create --name "Tech Corp" [--description TEXT]
```

## JSON Output
All commands support `--json` at the root level. Success payloads are the API
response as-is (`success`, `data`, `pagination` ...). Errors are printed as JSON
on stdout with exit code 1:
```json
{"error": "This assertion has already been revoked", "status": 409}
```
Validation failures add an `errors` object keyed by field.

## Common Agent Patterns

### Find the badge template, then issue
```bash
cli-anything-issuebadge --json badge list
cli-anything-issuebadge --json issue create --badge-id <id> --name "Ada Lovelace" --email ada@example.com --meta score=95
```

### Bulk issue from a spreadsheet export, safely re-runnable
```bash
cli-anything-issuebadge --json issue bulk --badge-id <id> --csv graduates.csv --idempotency-prefix cohort-2026-q3
```

### Download the certificate for an issue
```bash
cli-anything-issuebadge --json certificate download <issue-id> --out ada.pdf
```

### Revoke, then audit
```bash
cli-anything-issuebadge --json issue revoke <issue-id> --reason "Issued in error"
cli-anything-issuebadge --json issue history <issue-id>
```

### Print once, repoint later
```bash
cli-anything-issuebadge --json qrcode create --name "Event poster" --type url --data url=https://example.com/v1
cli-anything-issuebadge --json qrcode image <code> --out poster-qr.svg --format svg
cli-anything-issuebadge --json qrcode update <code> --data url=https://example.com/v2
```

## Interactive REPL
```bash
cli-anything-issuebadge   # No subcommand → enters REPL
```
Type commands without the `cli-anything-issuebadge` prefix. Type `exit` or `quit` to leave.

## Notes
- IDs are opaque strings (`badge list` → `id`, `issue list` → `issue_id`, `qrcode list` → `code`).
- `issue create` emails the recipient when `--email` is set; omit it for silent issuance.
- `issue revoke` on an already-revoked issue returns 409; use `issue update --reinstate` to undo a revocation.
- `certificate download` returns 404 when the badge has no certificate design.
- The API allows 60 QR requests per minute per account.
- Pretty output truncates long values (for example `image_base64`); use `--json` to get everything.
