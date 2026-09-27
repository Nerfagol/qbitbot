# Backup, upgrades and recovery

Backups contain private chat IDs and service credentials. Keep them outside Git,
restrict access, and keep another encrypted copy off the application host.

## Bot state

The image includes `backup_state.py`. It uses SQLite online backup, including
committed WAL data, and verifies each file's integrity and SHA-256 checksum.
Each database is individually consistent; the three snapshots are not one atomic
transaction. Stop the bot first if you need a quiet point across all three.

```sh
docker compose stop bot
docker compose run --rm --no-deps bot python backup_state.py \
  --watch-db /state/watches.sqlite3 --destination /state/backup-2026-09-27
mkdir -m 700 backups
docker compose cp bot:/state/backup-2026-09-27 backups/
docker compose up -d bot
```

Choose a new destination each time. Existing destinations are rejected. The backup
contains `watches.sqlite3`, optional `health.sqlite3` and `preferences.sqlite3`, and
`manifest.json`; absent optional files are recorded explicitly. The watch database
must already exist. No torrent contents or service credentials are included.
For bot-only mode, add `-f compose.bot-only.yaml` to each Compose command.

## Service configuration and downloaded files

Privately save `.env`, `bot.env`, Compose overrides and the current Git release/tag.
Stop qBittorrent and Jackett before copying their complete configuration directories:

```sh
docker compose stop bot qbittorrent jackett
docker compose cp qbittorrent:/config backups/qbittorrent-config
docker compose cp jackett:/config backups/jackett-config
chmod -R go-rwx backups
docker compose up -d
```

These configurations include authentication material and torrent resume state.
Back up the host download directory separately if you need media recovery; these
commands do not include it. Keep its paths consistent with qBittorrent's `/downloads`
mapping. Bot-only deployments need equivalent service-specific configuration backups.

## Code upgrades and rollback

Keep the previous checkout/image and a verified private backup. Stop the bot, select
the desired release, build, then use `docker compose up -d --no-deps bot` to recreate
it with the same state volume. Use the bot-only file when applicable. Ordinary code
rollback retains current state; it does not restore an older database snapshot.
Watch schema v1 and optional notice metadata remain compatible with the original
public baseline. Language preferences live separately and survive that rollback.

**Never use `docker compose down -v` for an upgrade: it deletes named state and
configuration volumes.** Never start two pollers with the same Telegram token.

## Deliberate snapshot restore

Stop the bot. First preserve its current state as another verified backup. Validate
`manifest.json` hashes and run `PRAGMA integrity_check` on each snapshot. Restore
into a **new** private state directory/volume, not over a live database. Map backup
names to the default runtime names:

| Backup | Runtime name under `/state` |
| --- | --- |
| `watches.sqlite3` | `watches.sqlite3` |
| `health.sqlite3` | `watches.health.sqlite3` |
| `preferences.sqlite3` | `watches.preferences.sqlite3` |

Use the corresponding siblings for a customized `WATCH_DB_PATH`. Keep directory
mode 700, files 600, and ownership readable/writable by the bot container. Point a
reviewed Compose volume override at the new volume, start one bot and verify
Downloads, Health and Language. Retain the previous volume until recovery is accepted.
An older snapshot intentionally loses later subscriptions and may repeat already
sent notices: delivery is at least once, not exactly once.

`make integration-public` rehearses fresh volumes, replacement, original-public-code
rollback, preserved preferences and deliberate restore without touching user data.
