# Source layout

Keep files with the responsibility that owns them:

```text
qbitbot/                    Runtime package
  __main__.py               Bot entry point
  app.py                    Telegram handlers and service integration
  downloads.py, search_ui.py User interactions and rendering
  health.py, monitoring.py  Background checks and delivery lifecycle
  watch_store.py            Durable watches and pending notices
  settings.py               Environment validation
  i18n.py, language_ui.py    Translation and language selection
  preferences.py            Durable language preferences
  locales/                  English/Russian JSON catalogs
  cli/                      Setup checks and state backups
tests/                     Offline tests and shared test fixtures
integration/               Disposable Docker verification and probes
docs/                      Guides, assets and historical plans
```

## Placement rules

- Put production Python in `qbitbot/`; import it through `qbitbot.*`.
- Keep CLI entry points in `qbitbot/cli/`, with argument parsing in `main()` and a
  `__name__` guard. Package imports must not start polling or load configuration.
- Keep feature modules flat until a responsibility needs several closely related
  modules. Avoid generic `utils/` folders and duplicate compatibility wrappers.
- Put offline cases in `tests/test_<area>.py`; keep container orchestration and
  disposable service fixtures under `integration/`.
- Keep packaged resources next to runtime code and resolve them relative to the
  module. Runtime state and secrets belong outside the source package.
- Reserve the root for Compose/build/tool configuration, dependency locks, examples,
  license/version information, README and contributor/handoff files.

## Running from source

After installing `requirements-dev.lock` into `.venv`, run from the repository root:

```sh
.venv/bin/python -m qbitbot
.venv/bin/python -m qbitbot.cli.setup_check --language en
.venv/bin/python -m qbitbot.cli.backup_state --help
make check
```

The bot needs configured credentials and service access; importing `qbitbot` itself
is inert. `bot.env` and relative state paths retain their working-directory semantics.
Docker uses the same module entry point from `/app`; Compose volume mappings are unchanged.
For example, container diagnostics use
`docker compose run --rm --no-deps bot python -m qbitbot.cli.setup_check`.
These commands replace the root script paths in v0.3.0; use that tag's own guides
when operating the older image. No installed wheel or console-script command is required.

## Verifying changes

`make check` includes compilation of every runtime module. Ruff excludes only the
legacy `qbitbot/app.py`, whose CRLF and formatting are preserved. Docker checks build
with the allowlisted package sources and catalogs. Stage newly added files before
`make integration-public`: its clean checkout export deliberately includes tracked
source only. Historical plans and source inventories keep their original paths;
the recovery harness still tests the original public code from Git history.
