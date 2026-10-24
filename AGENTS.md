# Repository Guidelines

## Project and structure

Python 3.12 Telegram bot using Jackett search and qBittorrent downloads.

- `src/qbitbot/`: runtime package; `app.py` owns handlers and feature I/O boundaries. Search,
  downloads, health, monitoring and storage retain their separate modules.
- `src/qbitbot/clients/`: narrow service configs, authentication/session/search protocols.
- `src/qbitbot/startup.py`: explicit env loading, settings injection and application wiring.
- `src/qbitbot/cli/`: maintenance commands; run with `python -m qbitbot.cli.<name>`.
- `src/qbitbot/locales/`: matched English/Russian catalogs; pass language explicitly
  and preserve queued notice payloads. `preferences.py` owns the language database.
- `src/qbitbot/http_safety.py`: DNS-pinned metadata requests and decoded body limits.
- `tests/`: offline tests with synthetic data; `integration/`: disposable Docker checks.
- `deploy/`: all image recipes and optional Compose variants; use root context.
- `config/`, `requirements/`: public templates and reviewed dependency locks.
- `docs/`: indexed guides; development/agent notes and historical archive.

The runtime package lives under src/qbitbot; development uses an editable install
and container/runtime verification uses a regular wheel install. Keep executable
Python out of the repository root. Reserve the root for build/tool
configuration, package metadata, the default Compose file and project/contributor documentation.
Deployment recipes/variants belong in deploy/, templates in config/, and reviewed
locks in requirements/. Reopened Dockerignore parent directories must re-exclude
children before exact allow rules. Stdin build archives require their own explicit
input allowlist; make compose-check tests actual directory-context exclusions.
Current docs have an index at docs/README.md; historical
evidence lives in docs/archive/. All image builds use repository-root context.
Use `qbitbot.*` imports; handler/client/startup imports must not read personal
configuration, validate environment, open databases/network or start polling.
startup.load_runtime/configure_handlers/build_application own explicit startup;
configure each handler module once before its poller runs. Keep allowlist and
client protocol checks at their existing boundaries.
Add modules alongside their owning feature; create subpackages only for a cohesive
responsibility. See `docs/development/layout.md` for entry points and placement rules.

## Commands and conventions

Create `.venv`, then run `make install-dev` to install the locked tools and editable
package. Package version and Python/direct dependencies live in pyproject.toml;
requirements/build.lock pins the build-only backend. Use `make check` for tests,
lint/format checks, compilation and dependencies. `make compose-check`, `make integration`
and `make integration-public` require Docker; the last also requires Compose 2.24.4+
and full public Git history for rollback. Stage new files before the public-stack
check, which exports tracked source. `python -m qbitbot.cli.backup_state` creates
verified private SQLite snapshots. Setup and recovery guides are available in English and Russian.
Use four-space indentation, snake_case names and async Telegram handlers; run blocking
HTTP through `asyncio.to_thread`. Preserve `src/qbitbot/app.py` CRLF and avoid
unrelated legacy formatting. Run `make format` for other Python modules and tests.

## Constraints

Only reviewed public source belongs here. Never import private history, deployment
reports, environment files, databases, logs, backups or real user/torrent fixtures.
Keep secrets outside Git and image layers. Unit tests block network access; integration
checks own their resources and must never prune globally or touch existing services.
Preserve allowlists, owner-bound callbacks, target identity checks, explicit download
and file-deletion confirmations, watch schema compatibility and separate durable state.
No production tokens or deployments are authorized by ordinary test commands.
Build wheels from the declared package/locale allowlist. Never import personal
configuration into artifacts; do not restore root PYTHONPATH hacks. Historical
rollback readers may retain their explicit captured-source path only.
The bot runtime is UID/GID 1000 with read-only application storage. Existing state
ownership changes require the documented explicit offline/backup procedure; never
chown recursively at startup or discard state to work around permission errors.
Preserve the configured-Jackett-only private HTTP origin exception, DNS pinning,
redirect rules and decoded response limits. Optional QBIT_HOST_HEADER changes
only the trusted service HTTP Host; preserve its authentication, host allowlist
and TLS certificate validation. Service package fixes belong in image
builds, never startup. Optional FlareSolverr uses `deploy/compose.flaresolverr.yaml` with the bundled stack;
keep its API unpublished on a Jackett-only network and preserve strict TLS.
Bot-only invocations require `--project-directory . -f deploy/compose.bot-only.yaml`
from root. Preserve Compose project/volume identity when moving deployment inputs.
`integration/flaresolverr.py --image <image>` verifies browser JavaScript and TLS
rejection using only generated internal-network fixtures; host OpenSSL is required.
The security workflow audits dependencies/images weekly
and on changes; zero findings is dated evidence, not blanket security assurance.

## Agent workflow

Before substantial work, read this file, `docs/development/agent/memory.md`, recent relevant `docs/development/agent/progress.md`
entries and the actual source/configuration. Source, tests and Git history outrank
memory. Follow established conventions and verify assumptions. Do not silently change
architecture or claim completion without implementation and reasonable verification.
After substantial work, curate durable discoveries in `docs/development/agent/memory.md`, append a dated
newest-first handoff in `docs/development/agent/progress.md`, and update this guide only when persistent
instructions change. Do not update these files mechanically for trivial edits.
