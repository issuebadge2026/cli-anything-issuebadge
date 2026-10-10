# cli-anything-issuebadge

CLI harness that exposes the [IssueBadge](https://issuebadge.com) API to AI agents,
built for the [CLI-Anything](https://github.com/HKUDS/CLI-Anything) catalogue (CLI-Hub).

- Package and usage docs: [`cli_anything/issuebadge/README.md`](cli_anything/issuebadge/README.md)
- Agent skill: [`SKILL.md`](SKILL.md)
- Architecture: [`ISSUEBADGE.md`](ISSUEBADGE.md)
- Test plan and results: [`cli_anything/issuebadge/tests/TEST.md`](cli_anything/issuebadge/tests/TEST.md)

## Quick start

```bash
pip install cli-anything-issuebadge
export ISSUEBADGE_API_KEY="your-api-key"
cli-anything-issuebadge --json badge list
```

## Publishing to CLI-Anything

This repo follows the **standalone repo** route in CLI-Anything's
[CONTRIBUTING.md](https://github.com/HKUDS/CLI-Anything/blob/main/CONTRIBUTING.md).

- Package: [`cli-anything-issuebadge` on PyPI](https://pypi.org/project/cli-anything-issuebadge/)
- Registry entry: [`registry-entry.json`](registry-entry.json), submitted as
  [HKUDS/CLI-Anything#538](https://github.com/HKUDS/CLI-Anything/pull/538)

Releasing a new version: bump `version` in `setup.py`, run `python -m build`,
then `twine upload dist/*`, and bump `version` in the registry entry in a PR.

## License

MIT
