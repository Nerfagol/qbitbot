# Public Release Verification and Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the new project installs and recovers correctly, then publish only its reviewed public history and verified release.

**Architecture:** Exercise the real Compose files with isolated test overrides, generated data and a fake Telegram transport. Validate backup/rollback independently of code upgrades. Local audit precedes GitHub creation; remote CI precedes the final release tag.

**Tech Stack:** Docker Compose v2 on Linux amd64, Python/pytest, SQLite online backups, GitHub Actions, GitHub CLI, a pinned secret scanner.

**Spec:** [Approved design](../specs/2026-09-27-public-release-design.md); prerequisites: [packaging](2026-09-27-public-packaging.md) and [bilingual UI](2026-09-27-bilingual-interface.md).

## Global Constraints

- No public CI run depends on private NAS access or developer filesystem paths.
- Automated tests must not use real trackers or personal Telegram tokens.
- Create the GitHub repository and upload only after this publication check passes.
- Ordinary code rollback retains newer compatible state.
- Completion requires a clean public-history audit, passing checks, resolved licensing and a reproducible fresh install.
- A pushed repository alone is not a completed release.
- Retain the private accepted version and backups; do not import their artifacts.

## Review Focus

1. Test cleanup must never delete a user's resources: task 1 tests exact project labels/names and timeout cleanup.
2. A fresh install must not accidentally depend on workstation files: task 1 builds from an empty exported checkout and fresh volumes.
3. Restart/rollback must preserve preferences and queued notices: task 2 rehearses retained-state rollback and deliberate restore separately.
4. Secrets can exist in history, images or screenshots despite a clean working tree: task 3 scans all artifact classes before upload.
5. A failed remote CI run must not result in a success-tagged release: task 4 separates repository upload from version tagging.

## Files and responsibilities

- `integration/public_stack.py`, `integration/fixtures.py`, `integration/compose.test.yaml`: fresh-stack and recovery verification.
- `tests/test_public_stack_cleanup.py`, `tests/test_backup_state.py`: fail-safe harness and backup tests.
- `backup_state.py`: online backups of bot-owned SQLite files into a new private destination.
- `docs/backup.en.md`, `docs/backup.ru.md`, `docs/troubleshooting.en.md`, `docs/troubleshooting.ru.md`, `THIRD_PARTY_NOTICES.md`, `CHANGELOG.md`.
- `.github/workflows/check.yml`, `.github/workflows/containers.yml`, `.gitleaks.toml`, `docs/release-checklist.md`, `docs/assets/`.
- Finalize `README.md`, `VERSION`, bilingual setup guides and public agent memory/progress.

## Task 1: Fresh-stack and existing-service verification

**Files:** integration runner/fixtures/override, cleanup tests, Makefile.

**Interfaces:** `python integration/public_stack.py --docker docker [--context NAME] --scenario fresh|recovery|all`; zero exit requires all scenario assertions and successful scoped cleanup. Result JSON contains check names/statuses/versions only. `make integration-public` runs `--scenario all`.

- [x] Add failing cleanup tests for create-timeout after resource creation, partial startup and teardown failures; assert every deletion targets recorded project-owned resources, no global prune, and cleanup failures produce a nonzero exit. Run `pytest tests/test_public_stack_cleanup.py -q`; confirm expected missing-runner failures.
- [x] Implement a uniquely named/labelled Compose project, temporary checkout, generated settings and fresh volumes. Resolve build images before isolation; runtime networks must be `internal: true` with no published ports, external mounts or Docker socket. Override download storage to a new test volume and explicitly clear production port mappings. Validate resolved Compose before any startup and reject leaked ports/mounts/networks.
- [x] Start the real pinned qBittorrent and Jackett services. Capture temporary credentials privately and configure test-only authentication through their supported APIs/local config; keep CSRF/auth enabled. Read real Jackett capabilities without indexer queries; use a separate fixture endpoint for search results, never real tracker accounts. Disable in-container auto-updates, configure no live indexers, and verify blocked optional outbound checks cannot prevent local API readiness.
- [x] Replace only Telegram transport with a recorded fake in a test entry point; drive real application handlers/lifecycle for both languages. Exercise generated torrent add/identity, numbered selection, pause/resume, confirmed deletion, health checks and error recovery. Use fixture-generated content and local peers only. Confirm dependency-only startup with blank bot settings and special-character credentials/path handling from plan 1.
- [x] Verify bot-only Compose against the same disposable external test services: it starts no bundled services and preserves explicit endpoints. Exercise a dependency becoming unavailable after startup and recovery without rebuilding. Test duplicate-container cleanup tracking and state-directory ownership errors without weakening production permissions.
- [x] Run `make check` and `python integration/public_stack.py --docker docker --scenario fresh`; expected all synthetic/real-local-API assertions pass and no labelled resources remain. Run the documented setup commands from the fresh checkout, not the development tree. The recovery/all scenarios become acceptance requirements in task 2. Commit `test: verify fresh compose installs and existing-service mode`.

## Task 2: State backup, restart and rollback rehearsal

**Files:** `backup_state.py`, backup tests/guides, recovery scenario in `integration/public_stack.py`, Docker build inputs.

**Interfaces:** `backup_databases(watch_path: Path, destination: Path) -> dict[str, str]` creates a new mode-700 directory and mode-600 backups/checksum manifest. It uses SQLite online backup for watch DB and existing health/preferences siblings, requiring the watch DB and recording optional absence. Existing destinations are rejected. CLI: `python backup_state.py --watch-db PATH --destination PATH`; exit 0 only after integrity/checksum verification.

- [x] Write failing tests that committed data held in WAL is backed up, each output passes `PRAGMA integrity_check`, all three available DBs survive, existing destination files cannot be overwritten, optional absence is explicit, and the source remains unchanged. Run `pytest tests/test_backup_state.py -q`; confirm missing-function failures.
- [x] Implement individual online database backups, not raw live file copies. Clearly record that separate DB snapshots are individually consistent. Validate source readability and destination permissions; do not dump row contents into output. Use generic file names and hashes only in manifests, never tokens or deployment paths.
- [x] Add integration recovery assertions: queued synthetic completion plus health card/preference survive bot replacement, preference is not lost after restart, and code rollback to plan 1's public baseline image leaves newer state intact. Then restore the new image and verify preferences return. Verify watches remain schema v1 and old readers ignore supplemental files.
- [x] Rehearse disaster recovery into new test volumes using the snapshot with the bot stopped; assert explicitly that this older state is intentional. Record that older snapshots may lose later subscriptions or repeat notices. Never restore over live user state to demonstrate recovery.
- [x] Document credential/config backups separately from bot SQLite backup, including consistent qBittorrent/Jackett configuration snapshots while those services are stopped, local environment files and downloads policy. Backups stay private; do not imply media is included. Show bot-only stop/recreate and warn next to destructive volume-removal commands.
- [x] Run backup tests, `make integration-public` (fresh plus recovery), then `make check`. Commit `feat: provide verified state backups and recovery instructions`.

## Task 3: Public documentation, CI and privacy audit

**Files:** workflows, scanner config, bilingual guides, notices, generic screenshots, README, release checklist, public memory/progress.

**Interfaces:** CI `check` runs `make check`; CI `containers` runs isolated integration on an amd64 Linux Docker runner. Both use synthetic settings, least-privilege `contents: read`, pinned third-party actions and no real bot token. Local audit records live outside tracked history if they contain private match terms or paths.

- [x] Write workflows with version-pinned Python and full-commit-pinned actions; verify referenced actions/permissions from primary documentation at execution time. Container CI builds images and pulls pinned services before starting the internal test network. Bound job timeouts; upload only allowlisted sanitized result artifacts, never blanket logs/config/workspaces.
- [x] Complete English/Russian installation, configuration, recovery and troubleshooting guides. Show Linux amd64 as the tested platform only. Include loopback/headless access, credentials/bootstrap, connection failures, language switching, at-least-once notices and shared-library deletion semantics. Produce screenshots from generated fixtures or the fake transport; no real user/chat/torrent identifiers.
- [x] Confirm MIT text and third-party notices against actual locked packages and pinned images. Original authorship was user-confirmed; do not claim ownership of upstream components or silently relicense them. Record component/license/source links in `THIRD_PARTY_NOTICES.md`.
- [x] Choose and record an immutable scanner version; run it against the working/staged files and all public refs/history, with redacted output. Add narrow synthetic-fixture exceptions only after review. Separately check private identifier matches and forbidden file classes, image filesystem/layers and release archives; keep private match lists outside this repository. Inspect screenshot pixels/metadata manually.
- [x] If a real secret/private datum is found before upload, remove it from every affected public commit/artifact and rerun the full audit. Do not upload then delete it in a follow-up commit. Verify there are no Git alternates or hidden donor refs. Ensure the export inventory and omitted-test replacements match the final tree.
- [x] Run local CI-equivalent unit/container commands from a fresh checkout. Commit documentation/workflows, then rerun the full-history audit including that commit. Expected: zero unresolved findings, passing checks and no undeclared private dependencies. Commit message: `ci: verify public builds and document bilingual setup`.

## Task 4: GitHub publication and version 0.3 release

**Files:** `VERSION`, `CHANGELOG.md`, `docs/release-checklist.md`, reviewed release notes; Git metadata and remote repository.

**Interfaces:** Target repository is the authenticated user's new `qbitbot` repository. The reviewed public directory is the sole push source. Publish source/build instructions first; prebuilt registry distribution is not required for this release.

- [ ] Reconfirm authenticated GitHub owner and repository-name availability. If the name is occupied, do not push into or modify it; obtain another name. Verify current directory/top-level Git root, branch, tracked inventory and remote list all belong to the public repository. These are read checks, not a request to reauthorize already-authorized publication.
- [ ] After task 3 passes, create the public repository from this directory with GitHub CLI, attach its remote and push only `main`. Do not push donor refs or blanket `--mirror`/`--all`. Verify the remote file tree and root history match the audited public source.
- [ ] Wait for CI checks on the pushed commit and inspect their results. Fix failures with public-only changes and repeat relevant tests/audits. Do not tag or announce a successful release while checks are pending or failed. If a dedicated live test bot is provided, record EN/RU manual acceptance separately; absence must remain explicit, not a fabricated pass.
- [ ] Set `VERSION` to `0.3.0`, write release notes with tested platforms/checks/limitations, and commit `chore: prepare version 0.3.0`. Run final local checks/audit on this exact tree; push and require green remote CI on the exact release commit.
- [ ] Create annotated tag `v0.3.0` at that checked commit, push that tag, and publish a GitHub release with reviewed notes via a body file. Verify tag target and release assets contain only the reviewed source; include no environment files, database backups or private manifests. The earlier private v0.2 tag/snapshot is unchanged.
- [ ] Record the public repository/release links and actual verification results in public progress. Report any manual acceptance not performed and any unsupported platform explicitly. The public release is complete only after these checks, not after repository creation.

## Completion evidence

Record the exact public release commit/tag, image digests, Linux amd64 checks, both-language scenarios, recovery outcomes, clean-history audit result and CI run links. Keep secret-bearing diagnostic details and backup contents outside public records.
