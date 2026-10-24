# Source layout

Keep files with the responsibility that owns them:

```text
qbitbot/                    Runtime package (source imports stay unchanged)
  cli/                      Setup, backup and state-permission commands
  locales/                  English/Russian resources beside runtime code
tests/                      Offline behavior and regression cases
integration/                Disposable Docker verification and probes
deploy/
  docker/                   All bot/service Dockerfiles and solver patches
  compose.bot-only.yaml     Existing-service mode; use --project-directory .
  compose.flaresolverr.yaml Optional bundled-stack overlay
config/                     Public configuration templates
requirements/               Reviewed runtime/development locks
docs/
  README.md                 User/developer documentation index
  deployment/               Current operations and image inputs
  development/agent/        Agent memory and progress notes
  development/plans/        Active implementation plans
  licenses/                 Third-party notices
  archive/                  Dated audits, acceptance and historical designs
compose.yaml                Default bundled entry point
pyproject.toml              Shared Ruff/pytest settings
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
- Keep root entry points small: README, CHANGELOG, LICENSE, AGENTS, Makefile,
  pyproject.toml, VERSION and the default compose.yaml. Tool discovery dotfiles and
  .env.example stay at root. All Dockerfiles use repository-root build context.
- Keep dependency locks in requirements/, optional Compose files in deploy/,
  templates in config/ and detailed license notices in docs/licenses/. Keep durable
  agent notes in `docs/development/agent/memory.md` and handoffs in
  `docs/development/agent/progress.md`; configure pytest alongside Ruff in `pyproject.toml`.

## Running from source

After installing `requirements/dev.lock` into `.venv`, run from the repository root:

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

## Layout upgrades

See [deployment migration notes](../../deploy/README.md). Root-relative settings,
Compose project/volume identity and Docker build-context allowlists are compatibility
requirements. Runtime packaging, src layout and client extraction are a separate
phase; this migration does not change application imports or startup.
