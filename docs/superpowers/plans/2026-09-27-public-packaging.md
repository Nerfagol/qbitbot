# Public Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an independently versioned, reviewed source export with working bundled and bot-only Docker installations.

**Architecture:** Preserve the existing Python module boundaries and behavior. Add generic configuration validation and a diagnostic command around the bot, with separate Compose entry points for a three-service stack and existing services. Public history starts here; the source donor remains private.

**Tech Stack:** Python 3.12, existing pinned python-telegram-bot/requests/pytest/Ruff dependencies, SQLite, Docker Compose v2, LinuxServer qBittorrent/Jackett images.

**Spec:** [Approved public release design](../specs/2026-09-27-public-release-design.md)

## Global Constraints

- The new repository must have its own Git directory and fresh history.
- Do not clone, fork, create a worktree from, add a remote to, or push the private repository.
- Export only explicitly reviewed tracked runtime modules, dependency locks, build inputs, synthetic tests and generic test helpers.
- The first verification target is Linux amd64. Do not advertise unverified ARM or NAS platform support.
- Do not use host networking or personal NAS defaults.
- An empty or invalid allowlist must fail closed.
- Unit tests use synthetic settings and block networking.
- No private history, production service operations or real torrent mutations belong to these tasks.

## Review Focus

1. A symlink or innocently named fixture must not export private content: task 1 rejects symlinks and inventories every file.
2. A first-time user must start dependencies without bot credentials: task 3 tests dependency-only startup with blank bot settings.
3. Credentials containing `$`, `#`, spaces or quotes must survive configuration loading: tasks 2/3 test exact bytes without printing them.
4. Unwritable storage must report the actionable cause without changing existing data: task 2 tests a disposable write probe and sanitized errors.
5. Slow or unavailable services must not make diagnostics hang or enable unauthenticated access: tasks 2/3 bound checks and preserve authentication.

## Files and responsibilities

- Retain: `tg_torrent_bot.py`, `watch_store.py`, `monitoring.py`, `downloads.py`, `search_ui.py`, `health.py`; Python behavior remains here.
- Add: `settings.py` for pure configuration parsing; `setup_check.py` for external read checks and disposable state-directory write checks.
- Add: `compose.yaml`, `compose.bot-only.yaml`, `.env.example`, `bot.env.example`; infrastructure and bot secrets stay separate.
- Rewrite: `README.md`, `AGENTS.md`, `MEMORY.md`, `PROGRESS.md`, `Makefile`, `.gitignore`, `.dockerignore`; generic facts only.
- Add: `docs/development/source-inventory.md`, `docs/deployment/images.md`, `docs/setup.en.md`, `docs/setup.ru.md`.
- Add: `tests/test_settings.py`, `tests/test_setup_check.py`, `tests/test_compose.py`, `integration/compose_check.py`.
- Preserve audited regression tests; adapt generic `integration/run.py`/`probe.py` and cleanup tests. Keep private acceptance launchers out.

## Task 1: Audited source export and regression baseline

**Files:** the six retained runtime modules; `Dockerfile`, both dependency locks, `pyproject.toml`, `pytest.ini`, `.gitattributes`, audited `tests/`; generic files/inventory above.

**Interfaces:** Input is an explicitly supplied donor directory kept only in local execution context. Output is a reviewed relative-path inventory and runnable `make check`; no export tool or document embeds the donor path, commit identity or personal identifiers.

- [x] Verify the destination is the separate repository, has no donor remote/alternates and contains only reviewed planning documents. Build a candidate list from tracked regular files; reject symlinks, `.git`, environment/state/archive files and whole-directory copies.
- [x] Inspect each candidate before copying. Include the six runtime modules, lock/build/test configuration and behavior tests. Inspect integration helpers individually. Omit `integration/manual.py`, `integration/manual_fixtures.py` and `tests/test_manual_setup.py` initially; record their manual-stack coverage and planned generic replacement. Keep cleanup coverage when retaining its harness.
- [x] Scan approved candidates locally for secrets and private identifiers before writing destination files. Report paths/rule names only. Sanitize real torrent names in fixtures to generated names while preserving meaningful parser markers. Scan planning documents too.
- [x] Copy approved bytes and write `docs/development/source-inventory.md`: relative path, purpose, retained/adapted status, omitted coverage and replacement task. Keep any donor hash/path mapping outside the public tree. Preserve the root application's CRLF.
- [x] Write generic public guidance and ignore rules for settings, state, downloads, logs, test artifacts and local environments. Allow example settings explicitly. Add MIT `LICENSE` with copyright `2026 qbitbot contributors`; inventory external notices for plan 3. Use `0.3.0-dev` in `VERSION` until release acceptance.
- [x] Adapt retained integration harnesses to an optional Docker context and ordinary Linux Docker, preserving exact resource tracking/cleanup tests. Remove the workstation-specific engine-name restriction only together with assertions that every mutation targets newly created, uniquely labelled test resources. No hardcoded workstation CLI or paths remain in the public Makefile.
- [x] Create the destination's own Python 3.12 environment; install its development lock. Run `make check`. Expected: all retained tests, lint/format checks, compilation and dependency compatibility pass. Record the actual retained count and exclusions; do not inherit a private test count as evidence.
- [x] Commit only the reviewed inventory and files: `chore: establish audited public source baseline`. Capture this public commit locally for the rollback tests in plan 3.

## Task 2: Validated settings and safe diagnostics

**Files:** create `settings.py`, `setup_check.py`, both new unit test modules; modify root configuration/startup, `Dockerfile`, `.dockerignore`, `Makefile`.

**Interfaces:** `Settings` is a frozen dataclass with fields `bot_token: str`, `allowed_users: frozenset[int]`, `qbit_url: str`, `qbit_user: str`, `qbit_pass: str`, `jackett_url: str`, `jackett_key: str`, `watch_db_path: Path`, `watch_interval: int`, `missing_grace: int`, `search_timeout: int`, `torrent_timeout: int`, `torrent_max_bytes: int`, `savepath: str | None`, `category: str | None`. `read_settings(env: Mapping[str, str]) -> Settings`; `SettingsError` contains safe field/rule names only. `CheckResult(service: str, ok: bool, message_key: str)` is a frozen dataclass. `run_checks(settings: Settings) -> list[CheckResult]`; `setup_check.main(argv: Sequence[str] | None = None) -> int`.

- [x] Add failing tests: `test_allowlist_rejects_empty_or_partially_invalid` rejects `''`, `'101,oops'`, `'0'`, `'-1'`; positive IDs and duplicate elimination pass. `test_credentials_preserved` checks exact special-character strings. `test_numeric_and_url_errors_redacted` checks invalid/nonpositive intervals, malformed URLs and absent required credentials without values in exceptions. Permit only HTTP(S) service URLs.

  Representative assertions (all other required fields supplied by a synthetic `valid_env` fixture):
  ```python
  with pytest.raises(SettingsError, match='ALLOWED_USERS'):
      read_settings({**valid_env, 'ALLOWED_USERS': '101,oops'})
  assert read_settings({**valid_env, 'ALLOWED_USERS': '101,101'}).allowed_users == frozenset({101})
  secret = "test $literal #value 'quoted'"
  assert read_settings({**valid_env, 'QBIT_PASS': secret}).qbit_pass == secret
  ```
- [x] Run `.venv/bin/python -m pytest tests/test_settings.py tests/test_setup_check.py -q`; expected failures are missing new interfaces or missing validation, not accidental network calls.
- [x] Implement pure parsing with existing defaults: watch interval 30 seconds, missing grace 600 seconds, search timeout 25 seconds, torrent timeout 25 seconds and limit 8388608 bytes. Preserve existing env names and root constants/adapters; optional category/savepath remain optional. Configuration validation runs before a Telegram poller starts. Do not make import perform network calls.
- [x] Test then implement setup checks for authenticated qBittorrent version, Jackett capabilities and state directory access; use temporary files removed in `finally`, never write into an existing database. Each HTTP check gets at most three attempts, connect/read timeouts 5/10 seconds, 2-second delays; authentication errors do not retry. Exit 0 only if all checks pass, otherwise 1. No Telegram sends/polling or torrent mutations.
- [x] Pin `test_probe_leaves_existing_database_unchanged`, `test_permission_error_is_actionable`, `test_http_timeout_is_bounded`, `test_wrong_password_does_not_echo_response` and `test_no_api_mutations` with fake boundaries. Use mocked permissions rather than assuming tests run as a non-root user.
- [x] Run targeted tests and `make check`; expected all pass. Commit: `feat: validate setup and report safe connection diagnostics`.

## Task 3: Bundled and existing-service Compose installations

**Files:** create both Compose files, example settings, `tests/test_compose.py`, `integration/compose_check.py`, setup guides and image record; update build context and Makefile.

**Interfaces:** `compose.yaml` exposes services `bot`, `qbittorrent`, `jackett`; `compose.bot-only.yaml` exposes only `bot`. `.env` contains infrastructure settings; ignored `bot.env` contains bot/API credentials. `python integration/compose_check.py --docker docker [--context NAME]` validates synthetic resolved configuration without displaying it. `make compose-check` invokes that command.

- [x] Write failing tests for exactly three versus one services, separate state/config volumes, no bot download mount, no fixed container names/host networking, loopback web bindings, matched qBittorrent internal/published WebUI and peer ports, TCP+UDP peer mappings, and no bot credentials passed to sibling services. Run `pytest tests/test_compose.py -q`; confirm relevant failures.
- [x] Resolve and record amd64-capable immutable digests for Python and both LinuxServer images; inspect installed healthcheck tools against those exact images. Use the tested digests in committed build/Compose files, not floating `latest`. Record versions/digests and the checks in `docs/deployment/images.md`; future changes require deliberate retesting.
- [x] Implement bundled settings: `WEB_BIND_ADDRESS=127.0.0.1`, `QBIT_WEBUI_PORT=8080`, `JACKETT_WEBUI_PORT=9117`, `TORRENT_PORT=6881`, `PUID=1000`, `PGID=1000`, `TZ=Etc/UTC`, `DOWNLOADS_DIR=./downloads`. Match qBittorrent internal WebUI port to its configured published port. Use long bind syntax for `/downloads`. Set Jackett `AUTO_UPDATE=false` for reproducible images. Bot endpoints use service DNS; bot-only endpoints come solely from `bot.env`.
- [x] Use named volumes `bot-state`, `qbit-config`, `jackett-config`; `/state/watches.sqlite3` for bot state. Do not specify bot credentials using required Compose interpolation: blank settings must allow `up -d qbittorrent jackett`. Validate bot settings inside the bot instead. Keep credentials in bot-only `env_file`, document Compose-safe single quoting, and test literal dollar/hash/space/quote round trips through actual Compose.
- [x] Implement dependency HTTP healthchecks (10-second interval, 5-second timeout, 12 retries, 30-second start period) and `service_healthy` conditions for bundled bot startup. Probe UI reachability without credentials in command arguments; authenticated health remains the bot's responsibility. Use the HTTP client verified in the pinned images. Preserve existing runtime retry behavior when dependencies fail later. Bot-only has no bundled dependencies.
- [x] Add bilingual dependency-first instructions: copy both examples; start dependencies; change qBittorrent's temporary password through its UI; configure Jackett; fill `bot.env`; run `docker compose run --rm --no-deps bot python setup_check.py`; then `docker compose up -d`. Explain how to access loopback-only interfaces remotely, change ownership/bindings, and never share raw bootstrap logs.
- [x] Run `make compose-check` with synthetic credentials, including path spaces/special characters and blank-credential dependency startup. Confirm JSON/config output is captured, not printed. Run `make check`, build bot and execute the inherited isolated API checks against disposable resources. Expected: both Compose entry points validate; dependency-only startup works; real authenticated API checks pass. Commit: `feat: package bot qbittorrent and jackett as one stack`.

## Milestone acceptance

Packaging is complete only after retained regression tests and disposable container checks pass. Russian UI remains the existing baseline at this milestone; bilingual rendering is plan 2. Do not publish yet.

## References checked during planning

- [LinuxServer qBittorrent](https://docs.linuxserver.io/images/docker-qbittorrent/): temporary-password setup and matching WebUI/peer port configuration.
- [LinuxServer Jackett](https://docs.linuxserver.io/images/docker-jackett/): configuration persistence, user/group settings and in-container update option.
- [Docker Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/): health-dependent startup.
