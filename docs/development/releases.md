# Public release checklist

Run from the independent public checkout. Never import deployment environments,
private Git refs, diagnostic reports or database snapshots into a release.

## Release preparation

The latest published release is [v0.4.0](https://github.com/Nerfagol/qbitbot/releases/tag/v0.4.0),
with matching package version and public amd64 GHCR images in one `qbitbot`
package with component tags. Its exact source
commite342894 passed all4 workflows and publication, anonymous manifest/pull and
QNAP checks. The release asset records immutable digests. v0.3.0 remains unchanged.
The additional single-package manifest records consolidated0.4.0 locations;
original source/tag/images retain their digests and build labels.
For each later release, choose a new version, update
`[project].version` and date its changelog notes. Keep package, Git tag and Docker
version tags aligned. Never overwrite an existing release tag or version image.

README badges track main; verify the intended release commit separately. Keep the
English/Russian installation and upgrade guides aligned. The supported verified
container target remains Linux amd64. Default Compose builds from source;
[registry overlays and publication requirements](../deployment/registry.md)
provide the prebuilt-image path. Check actual package visibility; if private, the
owner must make it public before anonymous/QNAP pulls can be verified.

## Verification

- `make check`: offline behavior/regressions, catalog parity, lint/format, compilation and dependency compatibility.
- `make compose-check`: actual Compose parsing, blank bootstrap, literal credentials, paths and ports.
- `make integration`: generated torrent/API, notification restart and application rollback.
- `make integration-public`: fresh exported checkout, real qBittorrent/Jackett, both languages, bot-only mode, service outage, three-database backup and new-volume recovery.
- `make wheel`: build the installable distribution; offline tests rebuild its sdist,
  inspect metadata/resources and reject generated private-file canaries.
- Repeat CI-equivalent commands from a fresh clone. Preserve Git history for public-baseline rollback.
- Inspect the generated preview pixels and metadata; record real Telegram acceptance separately.

Only Linux amd64 containers are accepted. Automated scenarios have no live tracker
accounts or Telegram token and cannot prove real Telegram delivery. The separate
[operator-confirmed v0.3.0 live acceptance](../archive/acceptance-v0.3.0.md) supplements those checks.

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

`publish.yml` runs on stable version tags or manual dispatch at such a tag. Its
read-only gate requires check/containers/security/codeql success on the exact main
commit and validates tag/package/changelog agreement. A separate job gets only
contents:read and packages:write, refuses existing version images, builds amd64
images, verifies synthetic Jackett/browser behavior and scans exact images before
upload. The ephemeral workflow token is used only for registry/API operations.
Verify anonymous pulls and QNAP compatibility before publishing the GitHub release.

Workflow permissions default to `contents: read`; only the CodeQL analysis job adds
`security-events: write` to upload code-scanning results. Actions are full-commit
pinned and Python is 3.12.15. Checkout disables persisted credentials. Container
and secret-scanning CI fetch complete public history. No raw findings, logs,
environments or workspaces are uploaded as artifacts. See upstream
[checkout](https://github.com/actions/checkout) and
[setup-python](https://github.com/actions/setup-python) documentation.

The security workflow runs independent jobs so secret/dependency-review failures
do not prevent the existing Python dependency and runtime-image audits:

- Gitleaks 8.30.1 is checksum verified and scans full public Git history and a
  tracked-source export on pushes, PRs, weekly schedules and manual dispatch.
  Output is fully redacted. The source scan still runs after a history finding;
  either scan failing fails the job. Local untracked files are not exported.
- PR dependency review rejects introduced vulnerabilities of low severity and
  above across runtime, development and unknown scopes. It uses the GitHub
  dependency graph, which must be enabled in repository settings. This supplements
  pip-audit: custom `requirements/*.lock` files still rely on the complete-lock
  audit. Dependency review neither posts PR comments nor enforces a license policy.
- A separate CodeQL workflow analyzes Python with `security-extended` queries on
  pushes, PRs, weekly schedules and manual dispatch. Dependabot branch pushes are
  excluded because their read-only tokens cannot upload results; their PR runs
  remain covered. Use advanced code-scanning
  setup for this workflow; disable any duplicate default CodeQL setup. Review
  findings in GitHub's Security tab. Configure code-scanning protection rules to
  block merges on alerts; a completed analysis alone does not mean zero findings.

Weekly Dependabot proposals update GitHub Actions pins only. Review and merge
them through the same checks; there is no automatic merge. Python dependency
updates must keep pyproject.toml and reviewed lock files consistent. Scanner
binaries downloaded directly by shell (Gitleaks/Trivy) need manual version and
checksum maintenance; Dependabot does not update these downloads.

After publishing these workflows, verify actual hosted runs and configure required
checks/protection rules in GitHub settings. Local lint/scanner results do not
prove those settings are enabled. See official
[CodeQL configuration](https://docs.github.com/en/code-security/reference/code-scanning/workflow-configuration-options),
[dependency review](https://github.com/actions/dependency-review-action) and
[Dependabot options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference).
The full manual privacy audit above, including built images/layers and private
identifier comparisons, remains required before release.

For an existing repository, prepare a new `[project].version` in `pyproject.toml` and update `CHANGELOG.md`
and rerun the checks and privacy audit on the intended release commit. Push only
reviewed changes, then wait for **check**, **containers**, **security** and **codeql**
workflows to pass on that exact commit and resolve security findings before creating
a new version tag. Require dependency review on the PR before merging. Existing release
tags, including `v0.3.0`, must not be altered. Record commit, new tag and CI links;
never describe pending CI or unperformed live acceptance as passed.

The original first-publication procedure and audit below are historical evidence.
They do not replace checks for the current release.

## Local audit evidence, 2026-09-27

Fresh independent clone: all 531 offline tests and all three Docker command groups
passed. Source/history/staged scans found no secrets. Image application files match
the explicit runtime/catalog/license allowlist. Every regular layer file was scanned;
the only two initial findings were the upstream Python **public** GPG signing
fingerprint repeated in image metadata, verified against the official Python image
Dockerfile and narrowly allowlisted for the artifact scan only. A dpkg text metadata
file with a `.gz` name was scanned as plain text rather than skipped. Final layer
scan had no errors or unresolved findings. PNGs contain only IHDR/IDAT/IEND chunks.
Private-marker comparison found no matches in public history and no forbidden file
classes; no Git alternates or donor refs exist. Re-run after release changes.

After independent review, compatibility/cleanup/language regressions increased the
suite to 539 passing tests. Affected Docker scenarios and rebuilt image-layer/source
audits passed again. Initial public GitHub check/container workflows both passed.
The release tag remains gated on green CI for its exact version commit.
