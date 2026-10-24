# Container runtime and offline state migration

The bot uses official Python 3.12.15 on Alpine 3.24, pinned by digest. It runs as
UID/GID **1000:1000**, with a read-only root filesystem, a 32 MiB temporary `/tmp`,
all Linux capabilities dropped, no privilege escalation, 256 MiB RAM, one CPU and
128 processes. `/state` is the only durable writable bot mount. Newly created
Docker named volumes inherit `/state` ownership from the image; bind mounts and
existing volumes require an explicit permission check/migration. PUID/PGID apply
to the bundled LinuxServer services, not the bot.

qBittorrent 5.3.0 and Jackett v0.24.2900 retain their reviewed upstream digests.
Small derived Dockerfiles apply only Brotli 1.2.1-r0 and musl/musl-utils 1.2.6-r3
from their upstream Alpine repositories at **build time**. `docker compose build`
builds these service images as well as the bot. A missing pinned package fails the
build; it never falls back to installing packages during startup. Rebuild/review
the pins when security updates arrive. LinuxServer init needs its existing root
setup; bot-only restrictions are deliberately not applied to those services.

## English: existing state volumes

This is an operator procedure, not an automatic startup action. Stop **all** bot
containers/readers/writers that share this state. First create and copy out a
verified private backup using the previously working image and the
[backup guide](../backup.en.md). Keep the existing state volume attached; do not
use `down -v`. Build the new image, then run this explicit offline maintenance
command on the stopped bot's volume:

```sh
docker compose stop bot
docker compose build bot
docker compose run --rm --no-deps --user 0:0 \
  --cap-add CHOWN --cap-add DAC_OVERRIDE --cap-add FOWNER \
  bot python -m qbitbot.cli.state_permissions --offline
docker compose run --rm --no-deps bot python -m qbitbot.cli.setup_check
docker compose up -d --no-deps bot
```

For bot-only installations add `-f compose.bot-only.yaml` to each Compose command.
The maintenance container temporarily adds only the capabilities needed to
change ownership and permissions; the normal bot retains no capabilities.
The utility fixes ownership to 1000:1000 and restricts directories to 0700/files
to 0600, including snapshots, without changing bytes or SQLite schemas. It rejects
symlinks, hardlinked files, special files and nested mounts before making changes.
It is for an **offline, trusted** volume; it does not lock out other containers or
protect against concurrent filesystem modifications. An interrupted migration can
be rerun after correcting the failure. Keep backups until normal startup and
pending notification/state checks succeed. Restore snapshots into a new private
volume owned by 1000:1000; old root containers can still read the migrated state. After running an older
root-based image, recheck/migrate ownership before upgrading again because it
may create new root-owned state or journal files.

## Русский: существующие тома состояния

Бот работает от UID/GID **1000:1000**. Новые именованные тома Docker получают
владельца из образа; существующие тома и bind mounts требуют проверки прав.
PUID/PGID меняют пользователей qBittorrent/Jackett, но не бота.

Остановите **все** контейнеры и процессы, использующие состояние. Сначала создайте
и скопируйте наружу проверенную закрытую резервную копию старым рабочим образом
по [инструкции](../backup.ru.md). Затем выполните команды выше; для режима bot-only
добавьте `-f compose.bot-only.yaml`. Не используйте `down -v`.

Команда с `--offline` явно подтверждает остановку всех читателей/писателей и
наличие копии. Она меняет только владельца на 1000:1000 и права на 0700 для
каталогов / 0600 для файлов, включая снимки; содержимое баз и схема не меняются.
Ссылки, специальные файлы и вложенные точки монтирования отклоняются до изменений.
Команда предназначена только для доверенного отключённого тома: она не блокирует
другие контейнеры и не защищает от одновременной подмены файлов. После прерывания
её можно повторить. Храните копию до проверки запуска и сохранённого состояния;
снимки восстанавливайте в новый закрытый том с владельцем 1000:1000.
