# Service clients and explicit startup

The runtime preserves one configured handler module per Telegram poller/process.
This refactor separates protocol and startup responsibilities; it does not introduce
hot configuration reload or multiple differently configured bots sharing handlers.

```text
python -m qbitbot
  startup.load_runtime              copy injected env, load bot.env, validate Settings
  startup.build_application
    configure_handlers              inject settings and independently configured clients
    register existing callbacks     sequential controls and existing background jobs
  run_polling                       post-init opens state and restores monitoring

app handler I/O boundaries
  clients.qbittorrent               session/auth, list/control/add/file protocol
  clients.jackett                   bounded JSON/Torznab requests and parsing
  search_results                   shared safe coverage metadata for UI/health
```

## Configuration and imports

Importing app, startup or clients neither loads personal bot.env/environment nor
opens state/network/polling. Immutable package locale resources can still load.
Unconfigured handlers have an empty allowlist; service calls reject unconfigured
use. Main startup explicitly loads configuration before constructing Telegram.

load_runtime works on a copy of injected values; existing injected values keep
precedence over optional file values. configure_handlers receives validated Settings
and optional flags, creates no HTTP session/database, and composes client objects.
Do not call configure_handlers while its application/jobs are active. Tests may
supply a separate handler module to avoid sharing global handler state.

## qBittorrent

QBitConfig contains only the service URL, credentials, allowed Host and add defaults;
its repr excludes fields. QBitClient owns cached session age/relogin and the
existing auth/info/control/add implementations. Only accepted200/Ok or204/empty
login responses succeed; add failures and single-hash control validation retain
existing behavior. Proxy/netrc credentials and automatic redirects stay disabled.
The optional Host override preserves destination URL and TLS verification.

Handler helpers remain thin sync boundaries for asyncio.to_thread and feature
callbacks. Tests that verify protocol details patch the client; UI/identity/job
regressions continue to patch the handler-level boundary. Session lifecycle is
unchanged by this extraction; no hidden retries or bulk-control semantics added.

## Jackett

JackettConfig contains URL, API key and timeout with secret-safe repr. JackettClient
owns JSON-versus-custom-Torznab routing, original query parameters, parsers, safe
coverage results and bounded stream reads. Existing DNS pinning, exact trusted
origin, redirect limits, body caps and response context closure remain in use.
Shared SearchResults no longer depends on UI; its old UI import is reexported.
Handler lifecycle still owns safe last-search health (counts/time/failure only).

## Startup and recovery

Application construction keeps the same commands, callback patterns and sequential
handler defaults. Slow search/add remains per-user background work; access checks,
owner identity, explicit download/deletion confirmations and durable schemas/mounts
are unchanged. Maintenance CLI probes remain independent read-only checks.

Current integration probes explicitly configure handlers with generated settings.
The historical reader and synthetic source-rollback fixture retain their explicit
captured-source overrides. No test launches a production poller or changes NAS data.
All installed-package/context checks include the client subpackage and reject
private files. No runtime dependency was added or changed.
