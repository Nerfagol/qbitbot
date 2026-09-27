# qbitbot

Self-hosted Telegram search and download controls for Jackett and qBittorrent.
Version 0.3 is under development; installation packaging and bilingual UI are in progress.

## Development

Use Python 3.12. Create `.venv`, install `requirements-dev.lock`, then run `make check`.
Tests use synthetic configuration and block external networking.
Use `make integration` for disposable Docker API/recovery checks.

## Features

Search and filter releases, confirm downloads, inspect progress, pause/resume,
and explicitly confirm torrent-plus-files deletion. All allowlisted users administer
the connected qBittorrent library. Subscriptions and health cards persist in SQLite.
Direct Telegram torrent uploads and media-app integration are out of scope.

See the [release plan](docs/superpowers/plans/2026-09-27-public-release.md).
