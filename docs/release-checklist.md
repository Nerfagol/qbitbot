# Public release checklist

Run from the independent public checkout. Never import deployment environments,
private Git refs, diagnostic reports or database snapshots into a release.

## Verification

- `make check`: offline behavior/regressions, catalog parity, lint/format, compilation and dependency compatibility.
- `make compose-check`: actual Compose parsing, blank bootstrap, literal credentials, paths and ports.
- `make integration`: generated torrent/API, notification restart and application rollback.
- `make integration-public`: fresh exported checkout, real qBittorrent/Jackett, both languages, bot-only mode, service outage, three-database backup and new-volume recovery.
- Repeat CI-equivalent commands from a fresh clone. Preserve Git history for public-baseline rollback.
- Inspect the generated preview pixels and metadata; record real Telegram acceptance separately.

Only Linux amd64 containers are accepted. Automated scenarios have no live tracker
accounts or Telegram token and cannot prove real Telegram delivery.

## Privacy audit

Use Gitleaks **8.30.1**, Linux x64 archive SHA-256
`551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`.
Download from the [upstream release](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1)
and verify its checksum before execution. `.gitleaks.toml` extends default rules
without broad synthetic-fixture exceptions.

```sh
gitleaks git . --log-opts='--all --full-history' --redact
gitleaks git . --staged --redact
gitleaks dir /path/to/reviewed-source-export --redact
```

Scan all refs/history, staged/current exported files, the release archive, and built
image files **and layers**. Exclude untracked local environments from upload, not
from the audit of release contents. Separately compare private identifiers against
all public blobs using a local private match list; never commit that match list or
raw findings. Check forbidden file classes, image `/app` allowlist, PNG metadata,
`.git/objects/info/alternates`, refs and remotes. A clean scanner report alone is
not a privacy guarantee. Resolve every finding before upload.

## CI and publication

Workflow permissions are `contents: read`; actions are full-commit pinned and Python
is 3.12.12. Checkout disables persisted credentials. Container CI fetches complete
public history for rollback tests. No logs, environments or workspaces are uploaded
as artifacts. See upstream [checkout](https://github.com/actions/checkout) and
[setup-python](https://github.com/actions/setup-python) documentation.

Create only a new repository, push only reviewed `main`, and inspect CI on that exact
commit. Prepare `VERSION`/`CHANGELOG`, rerun local checks and audits, push, then wait
for **both** workflows to pass on the release commit before creating `v0.3.0`.
Publish the reviewed source/release notes only. Record commit, tag and CI links in
the handoff; never describe pending CI or unperformed live acceptance as passed.
