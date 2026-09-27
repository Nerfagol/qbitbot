# Troubleshooting

## The bot does not respond

Run `docker compose ps`, then `docker compose run --rm --no-deps bot python -m qbitbot.cli.setup_check`.
Check the token from BotFather and your numeric Telegram user ID in `ALLOWED_USERS`.
The allowlist is mandatory. Run only one polling container per token. Commands use
English names in both languages. Send `/start` or select `/language` to change copy.

## A service is unavailable

Use service names `qbittorrent` and `jackett` inside the bundled network. `localhost`
in a bot container points to that container. In bot-only mode, configure endpoints
reachable from its network. A qBittorrent temporary password changes on restart until
you set a permanent password in its web UI and update `bot.env`. Jackett requires its
API key and configured indexers. Keep web interfaces on loopback; use SSH port
forwarding for a headless host as shown in the setup guide.

For Russian diagnostics, add `--language ru` to `python -m qbitbot.cli.setup_check`. Errors show
safe field names/categories. Do not post raw Compose configuration, service logs,
URLs with API keys, environment files or database backups in issues.

## Search returns nothing or downloads wait

Configure and test your indexers in Jackett. Search status distinguishes no matches
from unavailable sources; a healthy Jackett API does not prove its trackers work.
Filters can hide results: clear quality/size filters and retry. Recommended sorting
prefers quality among releases with enough reported sources; source counts are not a
promise of current peer availability.

Receiving torrent metadata, checking files, waiting for peers and paused downloads
are separate states. Use Refresh and the details card. After sustained inactivity,
the bot offers another search; it does not silently replace or delete your torrent.
All allowlisted users can control the entire qBittorrent library. Deletion always
means torrent **and files**, and requires a named confirmation.

## Progress or Health looks stale

Progress survives bot restarts using SQLite. Health cards refresh hourly; the displayed
UTC check time makes stale data visible. A stopped bot cannot edit its own card.
Refreshes within 30 seconds share a service sample. Search-source status comes from
the latest search, not an hourly query to every indexer. A deleted Telegram card can
be recreated; blocked/revoked users stop receiving updates.

Check state-volume permissions if subscriptions cannot be saved. Keep all three
SQLite databases through upgrades. See [backup and recovery](backup.en.md).
Completion delivery retries after failures and can repeat after a crash; it is not
exactly once. Changing language affects future updates, not already queued notices.

## Supported environment

Automated acceptance covers Linux amd64 containers. Other architectures, remote
Docker daemons, live tracker accounts and real Telegram delivery for the public
release have not been accepted. Docker Compose must support `!override` for the test
harness (2.24.4 or later); the ordinary installation files do not require that tag.
