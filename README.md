# cli-anything-issuebadge

CLI harness that exposes the [IssueBadge](https://issuebadge.com) API to AI agents,
built for the [CLI-Anything](https://github.com/HKUDS/CLI-Anything) catalogue (CLI-Hub).

- Package and usage docs: [`cli_anything/issuebadge/README.md`](cli_anything/issuebadge/README.md)
- Agent skill: [`SKILL.md`](SKILL.md)
- Architecture: [`ISSUEBADGE.md`](ISSUEBADGE.md)
- Test plan and results: [`cli_anything/issuebadge/tests/TEST.md`](cli_anything/issuebadge/tests/TEST.md)

## Quick start

```bash
pip install git+https://github.com/issuebadge2026/cli-anything-issuebadge
export ISSUEBADGE_API_KEY="your-api-key"
cli-anything-issuebadge --json badge list
```

## Publishing to CLI-Anything

This repo follows the **standalone repo** route in CLI-Anything's
[CONTRIBUTING.md](https://github.com/HKUDS/CLI-Anything/blob/main/CONTRIBUTING.md):

1. Push this directory to a public GitHub repo (`issuebadge/cli-anything-issuebadge`)
   and confirm `pip install git+<repo-url>` works from a clean environment.
2. Optionally publish to PyPI (`python -m build && twine upload dist/*`) and switch
   `install_cmd` in `registry-entry.json` to `pip install cli-anything-issuebadge`.
3. Fork `HKUDS/CLI-Anything`, branch from `main`, append the object in
   [`registry-entry.json`](registry-entry.json) to the `clis` array of `registry.json`.
4. Open a PR, tick the "New Software CLI (standalone repo)" checklist in their
   template, and paste the `pytest -v` output from this repo.

The same tree also drops into their monorepo as `issuebadge/agent-harness/` if an
in-repo listing is preferred (then set `source_url` to `null`, `install_cmd` to the
`#subdirectory=issuebadge/agent-harness` form, and copy `SKILL.md` to
`skills/cli-anything-issuebadge/SKILL.md`).

## License

MIT
