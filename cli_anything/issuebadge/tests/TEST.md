# TEST.md — IssueBadge CLI Harness Test Plan & Results

## Test Strategy

| Layer | File | Network | Purpose |
|-------|------|---------|---------|
| Unit  | test_core.py | None (`requests.request` mocked) | Backend client, flag parsing, request shapes, output, error handling |
| E2E   | test_full_e2e.py | Real IssueBadge API | Connectivity, listings, QR lifecycle, issue lifecycle |

Run:
```bash
python -m pytest cli_anything/issuebadge/tests/test_core.py -v
ISSUEBADGE_API_KEY=... [ISSUEBADGE_BASE_URL=...] [ISSUEBADGE_E2E_BADGE_ID=...] \
  python -m pytest cli_anything/issuebadge/tests/test_full_e2e.py -v
```

## Unit Test Plan (`test_core.py`)

### TestBackend
- [x] Missing `ISSUEBADGE_API_KEY` raises a RuntimeError naming the variable
- [x] Default base URL is `https://app.issuebadge.com`
- [x] `ISSUEBADGE_BASE_URL` is honoured and trailing slash stripped
- [x] `--base-url` override wins over the environment
- [x] Requests carry `Authorization: Bearer`, `Accept: application/json` and the `/api/v1` prefix
- [x] Non-2xx with `{success:false,message}` becomes `ApiError` with status
- [x] Validation `errors` map is flattened into the message and kept in `to_dict()`
- [x] `success: false` with HTTP 200 is still an error
- [x] Empty 401 body yields a message mentioning `ISSUEBADGE_API_KEY`
- [x] `raw=True` returns bytes and sends `Accept: */*`
- [x] `raw=True` with a JSON error body raises `ApiError`
- [x] Transport errors become `ApiError("Could not reach …")`
- [x] `check_connectivity()` ok / bad key / no key

### TestCLIHelp
- [x] `--help` exits 0 for root and every group and key subcommand
- [x] Root help mentions IssueBadge and `--json`
- [x] `--version` prints 1.0.0

### TestServer
- [x] `server status --json` → `{"ok": true}`
- [x] Invalid key → `[ERROR]` and exit 1

### TestBadgeCLI
- [x] `badge list` → GET `/badge/getall`, JSON and table output
- [x] `badge show <id>` → GET `/badge/{id}`
- [x] `badge create` → multipart (`data` + `files[badge_logo]`, no JSON body)
- [x] Missing logo file is rejected before any request

### TestIssueCLI
- [x] `issue create` sends a compact body (no nulls) with `metadata` from repeated `--meta`
- [x] Malformed `--meta` rejected with a `key=value` hint
- [x] `--badge-id` and `--name` are required
- [x] `issue list` forwards filters and pagination; `--per-page` capped at 100
- [x] `issue show` / `issue history` hit the right routes
- [x] `issue revoke` → POST `/issue/revoke` with reason and comments
- [x] 409 on revoke → exit 1 with `{"status": 409}` JSON error
- [x] `issue update --reinstate --memo` → PATCH `/issue/{id}`
- [x] `issue update` with no fields fails locally without a request

### TestBulkIssue
- [x] CSV without a `name` column / with no rows is rejected
- [x] One request per row; extra columns become `metadata`; `--idempotency-prefix` yields `<prefix>-<row>`
- [x] A bad row does not stop the batch; summary counts; exit 1 when any row failed
- [x] API validation error is recorded on the failing row

### TestCertificateCLI
- [x] `certificate download` → POST `/certificate/generate`, PDF bytes written, size reported
- [x] 404 (no design) → exit 1 and no file written
- [x] `certificate batch` → POST `/certificate/batch/generate` with `issued_badge_uuids`

### TestQrcodeCLI
- [x] `qrcode create` builds `{name,type,data,is_active}`; `=` inside values preserved
- [x] Pretty output truncates `image_base64`
- [x] `--inactive` → `is_active: false`; unknown `--type` rejected
- [x] list / show / scans / delete routes and params
- [x] `qrcode update --data --inactive` → PATCH body; no-field update fails locally
- [x] `qrcode image` writes the file with `size`/`format` params; size range enforced

### TestOrganizationCLI
- [x] `organization list` uses POST `/organization/getall`
- [x] `organization create` sends name and description

### TestCrossCutting
- [x] Missing key → exit 1, JSON error, no request made
- [x] `--base-url` flag changes the host
- [x] Text-mode errors go to stderr as `Error: …`

## E2E Test Plan (`test_full_e2e.py`)

### TestConnectivity
- [ ] `server status` reports `ok` and a token type
- [ ] `python -m cli_anything.issuebadge` works as a subprocess

### TestListings
- [ ] `badge list`, `badge show` (first badge), `organization list`, `issue list --per-page 2`, `qrcode list`
- [ ] Unknown badge ID exits 1 with an HTTP status

### TestQrcodeLifecycle
- [ ] create → show → update (name + destination) → image png + svg → scans → delete → show now fails

### TestIssueLifecycle (needs `ISSUEBADGE_E2E_BADGE_ID`)
- [ ] create → same idempotency key returns the same issue → show → revoke → 409 on second revoke → reinstate → history shows both actions → listed by name → certificate PDF (skipped when the badge has no design)
- [ ] `issue bulk` from CSV issues every row

## Results

| Date | Suite | Command | Result |
|------|-------|---------|--------|
| 2026-10-09 | Unit | `pytest cli_anything/issuebadge/tests/test_core.py` | 67 passed |
| 2026-10-09 | E2E | `pytest cli_anything/issuebadge/tests/test_full_e2e.py` (no key) | 11 skipped (guard works) |
| 2026-10-09 | E2E | against app.issuebadge.com with `ISSUEBADGE_E2E_BADGE_ID` | 7 passed, 4 failed: `badge show`, `qrcode list`, QR lifecycle and `certificate download` all receive HTTP 500 from production (reproduced with raw curl; the QR API is not deployed there yet and `badge/{id}` + `certificate/*` error server-side). Connectivity, listings, issue create/idempotency/show/revoke/409/reinstate/history/list and bulk CSV all passed. |
| 2026-10-09 | E2E | same, `-k "not qrcode and not Qrcode"` | 7 passed, 2 failed (production 500 on `badge/{id}` and `certificate/generate`), 2 deselected |
