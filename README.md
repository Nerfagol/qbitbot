# qbitbot

Search torrents and manage qBittorrent downloads from Telegram, in English or Russian.
Run the bot, qBittorrent and Jackett together with Docker Compose, or connect the bot
to services you already operate.

[English setup](docs/setup.en.md) · [Установка на русском](docs/setup.ru.md)

## What it does

- Search Jackett, choose quality/size filters, compare release details and confirm a download.
- Use compact numbered buttons, progress cards, pause/resume and confirmed deletion.
- Receive completion notifications and keep an hourly service-health card.
- Detect English/Russian from Telegram or save a preference with `/language`.
- Preserve subscriptions, queued notifications, health cards and language choices through restarts.

All allowlisted users administer the entire connected qBittorrent library. Deletion
removes the torrent **and its files**, after confirmation. Jackett indexers require
manual setup; no tracker accounts or credentials are supplied. Direct Telegram file
uploads and media-app integration are outside this release.

## Preview

Synthetic examples rendered from the bot's message formatters; these are not live chats.

![English progress example](docs/assets/progress.en.png)
![Пример прогресса на русском](docs/assets/progress.ru.png)

## Operations

[Backup/restore](docs/backup.en.md) · [Копирование и восстановление](docs/backup.ru.md)

[Troubleshooting](docs/troubleshooting.en.md) · [Устранение неполадок](docs/troubleshooting.ru.md)

Tested platform: Linux amd64 containers. Automated checks use generated torrents,
local APIs and a fake Telegram transport. Real Telegram delivery for this public
version has not yet had manual acceptance. No prebuilt registry image is published;
Compose builds the bot from the reviewed source.

## Development

Use Python 3.12:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
make check
make compose-check
make integration
make integration-public
```

Unit tests block networking. Docker checks create and remove only their own isolated
resources. `make integration-public` requires Compose 2.24.4+ and Git history for its
original-public-code rollback rehearsal. See [contributor guidance](AGENTS.md),
[localization](docs/development/localization.md) and the [release checklist](docs/release-checklist.md).

## License

Original project code is MIT licensed. Dependencies and service images retain their
own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md).
