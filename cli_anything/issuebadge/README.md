# cli-anything-issuebadge

Agent-native command-line interface for [IssueBadge](https://issuebadge.com):
issue digital certificates and badges, revoke and reinstate them, download the
rendered PDFs, and manage dynamic QR codes. Built with the
[CLI-Anything](https://github.com/HKUDS/CLI-Anything) methodology: every command
supports `--json`, errors are structured, and no subcommand drops you into a REPL.

## Install

```bash
pip install cli-anything-issuebadge
export ISSUEBADGE_API_KEY="your-api-key"   # app.issuebadge.com → Developer → API keys
cli-anything-issuebadge server status
```

## Usage

```bash
cli-anything-issuebadge badge list
cli-anything-issuebadge --json issue create --badge-id <id> --name "Ada Lovelace" --email ada@example.com --meta score=95
cli-anything-issuebadge --json issue bulk --badge-id <id> --csv recipients.csv --idempotency-prefix cohort-1
cli-anything-issuebadge issue revoke <issue-id> --reason "Issued in error"
cli-anything-issuebadge issue update <issue-id> --reinstate
cli-anything-issuebadge certificate download <issue-id> --out certificate.pdf
cli-anything-issuebadge qrcode create --name "Poster" --type url --data url=https://example.com
cli-anything-issuebadge qrcode image <code> --out poster.svg --format svg
```

Run `cli-anything-issuebadge --help` or any `<group> --help` for the full reference,
or read `skills/SKILL.md` for agent-oriented usage patterns.

## Environment

| Variable | Required | Purpose |
|---|---|---|
| `ISSUEBADGE_API_KEY` | yes | Bearer token for the API |
| `ISSUEBADGE_BASE_URL` | no | API host, default `https://app.issuebadge.com` |

## Tests

```bash
pip install -e ".[dev]"
python -m pytest cli_anything/issuebadge/tests/test_core.py -v        # mocked, no key
ISSUEBADGE_API_KEY=... python -m pytest cli_anything/issuebadge/tests/test_full_e2e.py -v
```

Set `ISSUEBADGE_E2E_BADGE_ID` to also run the issue/certificate lifecycle tests
(they create, revoke and reinstate a real issued badge).
