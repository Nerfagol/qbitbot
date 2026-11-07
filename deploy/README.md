# Deployment inputs

Run all commands from the repository root. Only public templates and image inputs
belong here; keep real bot.env/.env, databases and downloads outside this folder.

- Root compose.yaml is the default bundled bot/qBittorrent/Jackett entry point.
- deploy/compose.bot-only.yaml connects the bot to existing services.
- deploy/compose.flaresolverr.yaml adds an optional browser to the bundled stack.
- deploy/docker/ owns all image recipes and solver build patches.
- deploy/compose.*ghcr.yaml overlays select versioned GHCR images without builds;
  see [registry commands and first-publication visibility](../docs/deployment/registry.md).

Follow the [setup guides](../docs/README.md) to fill credentials before startup.

The bundled Jackett image runs a best-effort tracker warm-up once per container
start, before its health gate lets the bot start. It makes one empty search through Jackett's API-key search endpoint across
configured indexers, without helper retries or periodic requests. A bot
restart does not trigger it. Set `JACKETT_WARMUP_ON_START=0` in Compose's `.env`
and recreate Jackett to disable it. Standalone uses of the derived image must
explicitly set `JACKETT_WARMUP_ON_START=1`; bot-only deployments cannot warm an
external Jackett automatically. See [limits](../docs/troubleshooting.en.md#slow-first-search).

```sh
# Bundled stack, after setup:
docker compose up -d --build
# Existing services: root project directory is required on every command.
docker compose --project-directory . -f deploy/compose.bot-only.yaml up -d --build
# Optional solver for the bundled stack:
docker compose -f compose.yaml -f deploy/compose.flaresolverr.yaml up -d --build
# Standalone bot image build:
docker build -f deploy/docker/bot.Dockerfile -t qbitbot:local .
```

## Upgrade from the former root layout

Image recipes, optional Compose files, examples and dependency locks have moved.
The default bundled command remains docker compose. Replace old bot-only commands
with `docker compose --project-directory . -f deploy/compose.bot-only.yaml ...`.
The project directory keeps root-relative bot.env/.env, build and download paths
and prevents the nested Compose file from choosing a new default project name.

Keep the checkout directory name, or preserve your explicit existing `-p`/
`COMPOSE_PROJECT_NAME`. Do not invent a new project name during this upgrade:
that would select different named volumes. Preserve all current volumes and mount
mappings. A repository layout update needs no database migration, secret move or
state ownership change; the separate offline ownership guide applies only when
upgrading an older root-running bot. Never use down -v to upgrade.

Replace `cp bot.env.example bot.env` with `cp config/bot.env.example bot.env`.
Install development dependencies from requirements/dev.lock. Runtime pins live in
requirements/runtime.lock. Custom builds must specify the new Dockerfile path
and retain repository-root context `.`. No registry image or NAS service is changed
by moving these source files.
