# Repository Guidelines

## Project and structure

Python 3.12 Telegram bot using Jackett search and qBittorrent downloads.

- `qbitbot/`: runtime package; `app.py` owns handlers/API integration. Search,
  downloads, health, monitoring and storage retain their separate modules.
- `qbitbot/cli/`: maintenance commands; run with `python -m qbitbot.cli.<name>`.
- `qbitbot/locales/`: matched English/Russian catalogs; pass language explicitly
  and preserve queued notice payloads. `preferences.py` owns the language database.
- `tests/`: offline tests with synthetic data; `integration/`: disposable Docker checks.
- `docs/`: user/developer guides, assets and historical plans.

Keep executable Python out of the repository root. Reserve the root for build/tool
configuration, dependency locks, Compose files and project/contributor documentation.
Use `qbitbot.*` imports; keep package initializers free of startup/configuration effects.
Add modules alongside their owning feature; create subpackages only for a cohesive
responsibility. See `docs/development/layout.md` for entry points and placement rules.

## Commands and conventions

Create `.venv` and install `requirements-dev.lock`. Use `make check` for tests,
lint/format checks, compilation and dependencies. `make compose-check`, `make integration`
and `make integration-public` require Docker; the last also requires Compose 2.24.4+
and full public Git history for rollback. Stage new files before the public-stack
check, which exports tracked source. `python -m qbitbot.cli.backup_state` creates
verified private SQLite snapshots. Setup and recovery guides are available in English and Russian.
Use four-space indentation, snake_case names and async Telegram handlers; run blocking
HTTP through `asyncio.to_thread`. Preserve `qbitbot/app.py` CRLF and avoid
unrelated legacy formatting. Run `make format` for other Python modules and tests.

## Constraints

Only reviewed public source belongs here. Never import private history, deployment
reports, environment files, databases, logs, backups or real user/torrent fixtures.
Keep secrets outside Git and image layers. Unit tests block network access; integration
checks own their resources and must never prune globally or touch existing services.
Preserve allowlists, owner-bound callbacks, target identity checks, explicit download
and file-deletion confirmations, watch schema compatibility and separate durable state.
No production tokens or deployments are authorized by ordinary test commands.

## Agent workflow

Before substantial work, read this file, `MEMORY.md`, recent relevant `PROGRESS.md`
entries and the actual source/configuration. Source, tests and Git history outrank
memory. Follow established conventions and verify assumptions. Do not silently change
architecture or claim completion without implementation and reasonable verification.
After substantial work, curate durable discoveries in `MEMORY.md`, append a dated
newest-first handoff in `PROGRESS.md`, and update this guide only when persistent
instructions change. Do not update these files mechanically for trivial edits.
