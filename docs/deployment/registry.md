# GHCR images

The release workflow publishes Linux **amd64** images from stable version tags
after the four existing workflows pass on that exact main commit. All components
use **one package**, `ghcr.io/nerfagol/qbitbot`, with separate image tags/containers:

| Service | Image |
| --- | --- |
| Bot | `ghcr.io/nerfagol/qbitbot:0.4.0` |
| qBittorrent | `ghcr.io/nerfagol/qbitbot:qbittorrent-0.4.0` |
| Jackett | `ghcr.io/nerfagol/qbitbot:jackett-0.4.0` |
| Optional FlareSolverr | `ghcr.io/nerfagol/qbitbot:flaresolverr-0.4.0` |

Version0.4.0 is public: anonymous manifests/pulls and QNAP compatibility were
verified. No registry login or personal token is needed. For future packages,
check actual visibility after publication. If a package is private, the owner
can make it public in GitHub package settings. A successful upload or repository
link alone does not prove anonymous availability. See [GitHub's visibility instructions](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility).

## Use release images

Registry overlays require **Docker Compose2.24.4+**. Run from this checkout's
root, after following the English/Russian setup guide for private `.env`,
`bot.env`, download ownership and indexer configuration. Default Compose still
builds from source. The overlays remove builds and preserve service settings,
project and volume names; keep any existing explicit project name on every command.
Set `QBITBOT_VERSION=0.4.0` in Compose's `.env` to choose a release. There is no
mutable `latest` tag. Version images must never be overwritten; full-source-SHA
tags and OCI source/revision/version labels identify their build inputs. Bot
source tags use `sha-<revision>`; companion source tags use
`<component>-sha-<revision>`, preventing component collisions in the same package.
Each image retains its upstream licenses and service isolation.

The0.4.0 companion images were copied into these tags without rebuilding or changing
their digests. The published Git tag is unchanged, so its original registry
overlays show the former package names. Use the current overlays/guide for the
single-package layout. The release's additional `images-0.4.0-single-package.json`
asset records current references; its original manifest remains historical evidence.
The three former companion packages were deleted after verified migration and
explicit owner approval. Their old pull URLs no longer work.

Bundled services:

```sh
docker compose -f compose.yaml -f deploy/compose.ghcr.yaml pull
docker compose -f compose.yaml -f deploy/compose.ghcr.yaml up -d --no-build qbittorrent jackett
docker compose -f compose.yaml -f deploy/compose.ghcr.yaml run --rm --no-deps bot python -m qbitbot.cli.setup_check
docker compose -f compose.yaml -f deploy/compose.ghcr.yaml up -d --no-build bot
```

Bot only, connecting to existing services:

```sh
docker compose --project-directory . -f deploy/compose.bot-only.yaml -f deploy/compose.bot-only.ghcr.yaml pull
docker compose --project-directory . -f deploy/compose.bot-only.yaml -f deploy/compose.bot-only.ghcr.yaml run --rm --no-deps bot python -m qbitbot.cli.setup_check
docker compose --project-directory . -f deploy/compose.bot-only.yaml -f deploy/compose.bot-only.ghcr.yaml up -d --no-build
```

For the optional solver, use all four files on every command:

```sh
docker compose -f compose.yaml -f deploy/compose.flaresolverr.yaml -f deploy/compose.ghcr.yaml -f deploy/compose.flaresolverr.ghcr.yaml pull
docker compose -f compose.yaml -f deploy/compose.flaresolverr.yaml -f deploy/compose.ghcr.yaml -f deploy/compose.flaresolverr.ghcr.yaml up -d --no-build flaresolverr jackett
```

Then run the setup check and start the bot with that same four-file command.
Restarting Jackett invokes its one startup warm-up; bot-only restarts do not.
No periodic tracker warm-up is added.

## Upgrade and rollback

Back up private service configuration and all three bot databases using the
[offline/verified backup procedure](../backup.en.md) first. Stop the existing bot
before replacement, preserve project/volume/network/download identity and retain
previous images. Select the new version, pull, run the setup check, then recreate
the affected services. Never use `down -v` or change state ownership at startup.
For rollback, select the retained previous version/digest with the same mounts;
database snapshot restoration is a separate explicit operation.

For a private custom deployment, image references can be pinned to the published
manifest digest (`image@sha256:...`) instead of a version tag. Verify the pulled
image's OCI revision/version labels and installed bot package version. Automated
API/browser tests do not establish real Telegram or live tracker acceptance.

## Release operator

Update pyproject.toml and the dated changelog first; keep the existingv0.3.0 tag
unchanged. Push the reviewed source, wait for check/containers/security/codeql
success on that exact main commit, then create its new stable version tag.
`publish.yml` validates this gate, refuses existing version image tags, builds all
four images, runs synthetic startup/browser checks and scans vulnerabilities and
secrets before upload. It uses only a job-scoped ephemeral `GITHUB_TOKEN` for
packages:write. No production credentials, build secrets or personal PAT is needed.

If an upload fails after some version tags exist, do not overwrite them. Inspect
the partial release and choose a new version for a new publication attempt.
Before marking the GitHub release published, verify anonymous pulls, manifests,
source/version labels and QNAP compatibility. Record any live acceptance still
pending. A successful scan is dated evidence, not a blanket security guarantee.

The manual `consolidate.yml` workflow verifies exact main CI and the public0.4.0
digest lock, then uses checksum-pinned regctl0.11.7 to copy manifests. Existing
equal tags are preserved; conflicts stop before writes. Its default `copy` mode
deletes nothing. A separately approved, owner-only `cleanup` mode can remove the
three former companion packages after validating all canonical tags and every
legacy version/tag. Deletion breaks old public pull URLs; obtain explicit owner
approval after migration verification before selecting cleanup. Unknown legacy
data stops the whole cleanup before any deletion.
