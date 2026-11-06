# CI security improvements

**Goal:** Add the security checks requested by the owner before Docker image
publication. Docker registry/release publishing is a later task.

**Design:** Keep the existing dependency/image audits intact. Add independent
secret and PR dependency jobs to security.yml, a Python CodeQL workflow, and
weekly GitHub Actions update proposals. Pin actions by verified upstream commit
and Gitleaks by the already reviewed release checksum. Use read-only permissions
except CodeQL's job-scoped security-events upload. Never use pull_request_target,
production credentials, automatic merges or raw finding artifacts.

**Approaches:** Extending only the current vulnerability scanners would miss
source analysis and secrets. Replacing the existing scanners would lose image
coverage. The owner selected additive security improvements first; Docker image
publication follows separately. Python dependency pins remain coordinated across
metadata and reviewed locks rather than being independently updated by Dependabot.

**Owner/execution:** Primary agent, current checkout; no other writers observed.
Configuration-only work is validated with upstream action manifests, actionlint
and real Gitleaks scans rather than tests that duplicate YAML values.

## Tasks

- [x] Add Python CodeQL on pushes, PRs, weekly schedule and manual dispatch;
  use security-extended queries and restrict write permission to its analysis job.
- [x] Add independent full-history and tracked-source Gitleaks scans with redacted
  output and no broad exclusions; add PR-only dependency review failing at low
  severity and above. Keep existing audit/image gates unchanged.
- [x] Add weekly Dependabot updates for GitHub Actions only; document capabilities,
  required repository settings, release gates and remaining manual privacy checks.
- [x] Validate workflow syntax, pins and permissions; run real scanner success and
  synthetic-secret failure/redaction checks outside the repository; run make check.
- [x] Review final diff and update durable agent memory/progress with actual
  evidence and the unverified GitHub-hosted checks.

## Review focus

- Fork PRs must use pull_request with no secrets or persistent Git credentials.
- Scan failures must not prevent the existing independent audits from running.
- Full public history and tracked source must both be scanned, excluding local
  untracked environments from the source export.
- Dependency-review snapshots/settings can differ on GitHub; local YAML checks
  cannot certify a successful hosted analysis or required-check configuration.
- No runtime pins, image publication, production services or state are changed.
