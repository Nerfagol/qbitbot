# Changelog

## Unreleased

- Organize runtime code and catalogs under `qbitbot/`, with maintenance commands in
  `qbitbot/cli/`. Start from a source checkout with `python -m qbitbot`; setup and
  backup commands now use `python -m qbitbot.cli.setup_check` and
  `python -m qbitbot.cli.backup_state`. Compose starts the new entry point automatically.
  Bot behavior, environment settings and persistent state formats remain unchanged.

## 0.3.0 — 2026-09-27

First public release, with independent source history and no deployment configuration.

- Bundled bot/qBittorrent/Jackett Compose installation and bot-only mode; pinned images, validated settings and safe bilingual setup checks. Controls require qBittorrent 5.x; tested with 5.1.2.
- English/Russian menus, search/filter/release details, numbered Downloads controls, progress/completion messages and hourly health cards. Language choices persist separately from watch state.
- Explicit download and torrent-plus-files deletion confirmation, owner-bound callbacks and allowlisted shared-library access.
- Restart-safe subscriptions and queued notices, online SQLite backups, retained-state code rollback and deliberate snapshot restore.
- Bilingual setup, troubleshooting and recovery guides; synthetic previews and pinned CI.

Verified: 539 offline tests, Compose credential/path checks, isolated real service APIs,
fresh installs, both-language handler flows, outages, restart, rollback and new-volume
restore on Linux amd64. Independent review findings were fixed and regression-tested.
Public history/source and image layers passed privacy scans with only a reviewed
upstream public signing fingerprint exception in the artifact audit.

Post-release verification (2026-09-27): operator-confirmed live Telegram acceptance
on a Linux amd64 NAS covers both languages, search/download controls, completion
messages, restart recovery and health-card interaction. See
[acceptance scope](docs/acceptance-v0.3.0.md).

Limits: other architectures are not verified. Notifications may repeat after a crash. No
prebuilt registry image, Telegram torrent-file upload or media-app integration is included.
