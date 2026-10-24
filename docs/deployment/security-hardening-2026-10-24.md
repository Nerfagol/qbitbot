# Local security hardening, 2026-10-24

This supersedes the unresolved local-candidate findings in the
[earlier maintenance audit](security-2026-10-24.md). Scope is the public deployment
candidate on Linux amd64/Docker Desktop. No NAS release, state volume, torrent,
service or Telegram poller was changed. Existing private v0.2 remains separate.

## What changed

The bot uses digest-pinned official Python 3.12.15 on Alpine 3.24 instead of the
larger Debian base. This removes unused OS packages without suppressing their
findings. The same pinned Python dependencies remain in use. Build-only pip is
removed after installation. Actual musl/SSL/SQLite behavior and the full offline
suite were tested, rather than assuming the libc change is transparent.

The image runs as UID/GID 1000:1000. Both Compose modes enforce a read-only root
filesystem, bounded temporary scratch space, all capabilities dropped,
no-new-privileges, 256 MiB RAM, one CPU and 128 processes. Only `/state` is durable
writable bot storage. Fresh volumes inherit ownership; existing volumes need the
explicit offline, backed-up migration in
[container hardening and state migration](container-hardening.md). Startup never
recursively changes ownership. Symlinks, hardlinks, nested mounts and special
files are rejected before migration. The migration is for a trusted volume with
all writers stopped; it cannot defend against concurrent filesystem replacement.
If a rollback uses an older root-based image, recheck/migrate permissions before
upgrading again, because that image may create root-owned journal/state files.

qBittorrent/Jackett retain reviewed upstream application digests in small derived
Dockerfiles. Only Brotli libraries and musl packages are upgraded to exact patched
versions during image build. LinuxServer initialization retains its required
upstream privileges; bot restrictions are not blindly applied to these images.

HTTP metadata requests now:

- Accept only bounded HTTP(S) URLs without credentials or control characters.
- Permit private addresses only for the exact configured Jackett origin. This
  exception supports internal Jackett torrent links; it is not a general LAN
  allowlist. Other private tracker URLs are deliberately rejected.
- Resolve DNS at connection time, reject nonglobal, site-local, multicast and
  private-address mappings, then connect to the exact checked sockaddr. Mixed
  public/private DNS answers are rejected, preventing DNS rebinding between
  checking and connecting. HTTPS retains normal SNI/certificate verification.
- Validate every redirect, including the magnet-discovery path; reject HTTPS
  downgrades. Search/capability redirects remain within their configured origin.
- Disable environment proxies/netrc and Requests' eager redirect-body buffering.
  qBittorrent authentication/setup sessions also disable ambient credentials and
  automatic redirects so login bodies cannot be forwarded elsewhere.
- Cap decoded search bodies at 4 MiB and capability XML at 256 KiB. The existing
  configurable torrent-metainfo cap defaults to 8 MiB. All streams/sessions close
  on failure. Limits also apply to chunked/compressed bodies with pinned urllib3.

A new read-only-permission GitHub workflow audits the complete dependency lock
and all three built images on pushes, pull requests and weekly. Trivy is version
and SHA256 pinned; scans do not suppress findings. The workflow itself has only
been checked locally and becomes active when the changes are published.

## Verification and scan results

- 609 offline tests/checks passed; all 609 also passed under the actual non-root
  Alpine/Python runtime with networking disabled and a read-only filesystem.
- Regression tests reproduced body-limit, Requests redirect buffering, proxy/
  redirect-policy, DNS/NAT64/site-local/multicast and migration boundary failures
  before their corresponding fixes. Independent reviews were addressed with
  failing-then-passing tests.
- Docker Compose configurations and literal credential/path handling passed.
  Real isolated qBittorrent API/add/control tests, root-owned old-state migration,
  unprivileged SSL/SQLite/scratch/storage restrictions, restart and rollback passed.
- Fresh English/Russian stacks, service outage/recovery, bot-only mode, online
  backup, deliberate restore and retained health/preferences/watch state passed.
  All generated containers/volumes/networks were cleaned by scoped ownership.
- A guarded read-only HTTPS request to official PyPI metadata succeeded with
  certificate verification, independently of synthetic network fixtures.
- Fresh pip-audit 2.10.1 reports no known advisories in the full development lock.
- Trivy 0.76.1 with database updated **2026-10-24 07:11 UTC** reports **zero
  vulnerability records in all three candidate images**, including OS and
  detected Python/.NET packages. No ignore rules or severity exclusions were used.

The earlier bot image had 164 OS records; its replacement has none in this scan.
The latest upstream service images each had one high Brotli and two unknown musl
records; the derived images have none after the pinned package upgrades.

## Limits and remaining configuration notes

A clean advisory scan is not proof against unknown vulnerabilities or a complete
reachability audit. NAS deployment and other CPU architectures remain unverified
for this candidate. SQLite schemas and application control semantics are preserved.

HTTP timeouts are per-operation/read limits, **not an overall deadline**. DNS,
multiple connection attempts and a slowly delivered response can take longer.
HTTP header limits remain those of the Python standard library. The trusted
service endpoints themselves remain an operator-controlled trust boundary.

Dockerfile configuration scanning still flags root in the two LinuxServer-derived
images (DS-0002), where upstream init uses root before service-user startup. This
is not a claim that those images are rootless. The bot no longer has that finding.
Dockerfile HEALTHCHECK absence remains a low-priority generic finding (DS-0026);
service healthchecks live in Compose. No dummy bot check was added to hide it:
Telegram polling liveness needs a separate, meaningful health design.

Image identities are recorded in [Container inputs](images.md). The original
maintenance report remains historical evidence, not the current security status.

## Subsequent optional browser support

The optional fourth image, its strict TLS patches, isolated Compose overlay,
public-source rebuild/synthetic browser verification and dated zero-record scan
are documented in [FlareSolverr setup/security](flaresolverr.md). The current full
application suite passes621 tests. A subsequent authorized Linux-amd64 deployment
also passed service readiness and indexer search checks; private configuration and
raw evidence are intentionally excluded from this repository. Earlier scope text
above describes the original local hardening verification, not later operations.
