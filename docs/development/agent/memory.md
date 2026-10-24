# Project Memory

## Architecture

Watch subscriptions and pending notices use SQLite schema v1; health cards use a
separate sibling database. Search and dashboard action sessions are ephemeral.
Control handlers are sequential; slow search/add work runs once per user in background.

## Conventions

Verify additions by metainfo hash, not title/list position. Only completed data in a
seeding/upload state counts as finished. Notice delivery is at least once across crashes.
Test tokens and fixture IDs are deliberately synthetic. Preserve required attribution.

## Environment

Use Python 3.12 and the pinned development lock. Container tests create their own
internal networks/volumes; they never connect to a personal deployment.

## Language persistence

Preferences live in a separate `.preferences.sqlite3` sibling of the watch DB.
Detected language and explicit overrides are persisted separately. Resolve the owner
when rendering; never translate a queued notice again during delivery retries.
See `docs/development/localization.md` for rendering boundaries.

## Recovery

`qbitbot.cli.backup_state` snapshots SQLite through its online API and rejects existing
destinations. Each DB is individually consistent; stop the bot for a quiet point
across all three. Ordinary code rollback retains current state. Snapshot restore
is separate and may replay notices. See bilingual backup guides for name mapping.

## Public release baseline

`v0.3.0` is the first public release; qBittorrent 5.x is required for controls
(v0.3.0 bundled 5.1.2; the current local candidate bundles 5.3.0). Release CI accepts Linux amd64 and uses only
synthetic Telegram transport. The operator confirmed live acceptance of the exact
v0.3.0 release on Linux amd64 on 2026-09-27, including completion delivery and normal
restart recovery; see `docs/archive/acceptance-v0.3.0.md`. This does not certify ARM or later
source revisions. Crash-time notification duplicates remain an expected limitation.

## Source layout and rollback fixtures

Runtime and catalogs live together in `qbitbot/`; see the layout guide for commands.
`bot.env` and relative state paths still resolve from the working directory, not the
package directory. The Docker working directory remains `/app` with state in `/state`.
The public recovery harness deliberately loads top-level `watch_store` only for its
historical `7267bcd` reader; current code uses `qbitbot.watch_store`. Keep that distinction
when editing rollback tests.

## Current local security candidate

- Runtime dependencies retain the reviewed 2026-10-24 pins (anyio 4.14.2,
  certifi 2026.10.19, idna 3.15, requests 2.33.0, urllib3 2.8.0); pytest 9.0.3
  includes Pygments 2.21.0. Fresh pip-audit/dependency checks report no findings.
- Docker/CI Python is 3.12.15; the current bot base is digest-pinned Alpine3.24.
  Build-only pip is removed. Bot UID/GID1000, read-only app, temporary scratch,
  no capabilities/privilege escalation and resource limits apply in both modes.
- Existing state needs explicit offline backed-up UID1000 migration, never a
  startup chown. See docs/deployment/container-hardening.md. Old root rollback
  images can create root-owned journals: recheck permissions before upgrading.
- Bundled qBittorrent5.3.0/Jackettv0.24.2900 use derived images that patch only
  pinned Brotli/musl packages during build. Upstream init privileges are retained.
  Runtime/setup support both HTTP204 empty and legacy200/Ok. responses.
- http_safety.py pins connections to validated DNS answers, with only configured
  Jackett origin allowed private addresses; rejects private mappings/site-local/
  multicast and unsafe redirects, disables proxy/netrc/eager redirect buffering,
  and caps decoded search/capability bodies. qBit auth redirects are disabled too.
- Initial hardening verification: 609 offline tests/checks, all609 also under
  non-root/read-only/network-disabled Alpine, plus API/recovery/fresh EN/RU checks.
  The subsequent existing-service connection fix passes621 offline checks and
  actual authorized amd64 NAS readiness/native-menu/restart/state checks.
- Optional QBIT_HOST_HEADER retains an existing service's allowed Host while
  QBIT_URL uses a reachable Docker route. Runtime/setup share validated authority
  handling; never disable Host/CSRF/authentication or TLS verification to connect.
  This changes HTTP Host only; TLS verifies the hostname in QBIT_URL.
- Trivy0.76.1 DB2026-10-24: all3 current candidate images have zero vulnerability
  records. LSIO root-init and absent Dockerfile HEALTHCHECK remain configuration
  findings; no dummy liveness check or vulnerability suppressions are used.
  HTTP timeouts remain per-operation, not a total deadline. See the dated
  docs/archive/security/security-hardening-2026-10-24.md for scope and limits.
- Security CI now audits dependencies and the3 base images plus optional FlareSolverr on changes/weekly, using a
  checksum-pinned scanner. Published in commit2cfd466; actual GitHub CI results
  have not been verified by the structural review.

## Optional FlareSolverr

The bundled-stack overlay builds official3.5.2 source on pinned Python3.11.17/
Alpine3.24 with matching Chromium/driver, updated CA/urllib3 and no installer.
Asserted patches preserve strict TLS and reject Chromium internal error pages.
API is unpublished on a Jackett-only network; UID1000/read-only/caps/NNP/limits
apply. Browser upstream no-sandbox remains a limitation; document this openly.
Synthetic browser JavaScript and selfsigned-TLS negative checks pass on amd64;
public-source rebuild scan reports zero records with the2026-10-24 database.
See docs/deployment/flaresolverr.md. No private deployment data belongs here.

## Contributor documentation placement

Agent notes live in docs/development/agent/memory.md and docs/development/agent/progress.md;
root AGENTS.md points to them. Pytest and Ruff share pyproject.toml. Preserve
root default Compose/tool entry points. All Dockerfiles/variants are in deploy/,
configuration templates in config/ and reviewed locks in requirements/.

## Structural review

The2026-10-24 report in docs/archive/reviews/structure-2026-10-24.md led to the
owner-approved deployment/documentation consolidation. Runtime package/src/client
refactoring is a separate future phase. Preserve Compose project/volume
identity, root-relative inputs, restricted build contexts and rollback fixtures.

## Applied deployment/documentation layout

Root has8 visible entry files. deploy/docker owns all image recipes, deploy/ the
optional Compose variants, config/ templates, requirements/ unchanged lock closures,
docs/licenses/ notices, development/agent notes and archive/ historical evidence.
Use repository-root build contexts and `--project-directory .` for standalone
bot-only Compose; preserve checkout or explicit project name and existing volumes.
All3 migrated Compose configurations were compared against old resolved settings;
only intended Dockerfile path differences remain. See deploy/README.md for upgrades.
Python runtime/source layout remains qbitbot/; src/client refactoring is not applied.

Dockerignore parent exceptions can admit descendants: re-exclude children before
allowing exact runtime inputs. compose-check exercises actual directory filtering
with synthetic private/required files. Raw stdin tar contexts bypass Docker CLI
filtering; integration archives must retain their explicit input allowlist.
