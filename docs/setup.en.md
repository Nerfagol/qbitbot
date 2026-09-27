# Installation

Install Docker Engine/Desktop with Compose v2. Use a Linux amd64 host for the
verified target. Download this repository and work from its root directory.

## Bundled bot, qBittorrent and Jackett

```sh
cp .env.example .env
cp bot.env.example bot.env
chmod 600 .env bot.env
mkdir -p downloads
```

Set `.env`'s `PUID`/`PGID` to the owner of your download folder (`id -u`, `id -g`).
Set `DOWNLOADS_DIR` to that writable directory. Set alternate WebUI/peer ports if
already occupied. Relative paths resolve from this project directory.

Start the two services first; bot credentials may still be blank:

```sh
docker compose up -d qbittorrent jackett
```

1. Open qBittorrent at `http://localhost:8080`. Its first-run `admin` password is
   in `docker compose logs qbittorrent`; read it locally and never paste raw logs
   into a public issue. Change the password in WebUI settings and retain authentication.
2. Open Jackett at `http://localhost:9117`. Configure your chosen indexers and copy
   its API key into `bot.env`. Private tracker accounts belong only in your installation.
3. Create your Telegram bot through BotFather. Put its token, your numeric Telegram
   user ID(s), qBittorrent username/password and Jackett key into `bot.env`.
   Allowed IDs are comma-separated; everyone allowed controls the shared torrent library.
4. Single-quote values containing `$`, `#` or spaces. Escape an inner single quote
   as `\'`. No credentials are shipped as defaults. Never commit `.env` or `bot.env`.

```sh
docker compose build bot
docker compose run --rm --no-deps bot python setup_check.py
docker compose up -d
```

The check authenticates to the APIs and probes state-directory access without
starting Telegram polling or adding torrents. If it reports a failure, fix that
setting first. Do not share `docker compose config` output: it resolves credentials.
Open `/start` in Telegram, then verify Search, Downloads and Health. The bot detects English/Russian from Telegram. Use `/language` to save a preference.

Web interfaces bind to localhost by default. For a headless host, forward ports
through SSH or set `WEB_BIND_ADDRESS` to the host's specific LAN address and secure
access there. Setting `0.0.0.0` exposes them on all host interfaces; do not expose
them directly to the Internet. Peer ports are separate TCP/UDP mappings.

## Existing qBittorrent and Jackett

Copy only `bot.env.example` to `bot.env`, fill the credentials/allowlist and set
reachable `QBIT_URL` and `JACKETT_TORZNAB_URL` values. `localhost` inside the bot
means that container, not your host. `QBIT_SAVEPATH` is a path inside qBittorrent.

```sh
docker compose -f compose.bot-only.yaml build
docker compose -f compose.bot-only.yaml run --rm bot python setup_check.py
docker compose -f compose.bot-only.yaml up -d
```

This starts only the bot. Do not run both entry points with the same Telegram token.

## Persistence

Normal `docker compose down` keeps named configuration/state volumes. Recreate
containers to upgrade while retaining those volumes. **`down -v` deletes named
state/config volumes**; it is not an upgrade command. Downloaded files live in the
configured host directory. Back up bot settings, each service's configuration and
all bot databases privately. Do not copy live SQLite files as an ordinary file backup.
