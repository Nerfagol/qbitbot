# GHCR release 0.4.0

Owner authorized the proposed registry workflow, new version/changelog, publication
and QNAP pull testing. Primary owns implementation and records; independent reviewer
owns read-only final review. Existing checkout is clean at8bbe6b5, with no other
writers. No runtime feature or database change is required.

Use0.4.0 for the accumulated features/security/layout changes since0.3.0. Keep the
existing tag unchanged. Publish only Linux amd64: ghcr.io/nerfagol/qbitbot and the
qbitbot-qbittorrent, qbitbot-jackett and qbitbot-flaresolverr companion packages.
Use version and full-source-SHA tags plus OCI source/revision/version labels.
Require existing check/containers/security/codeql success on the exact source SHA,
verify tag/package/changelog agreement and refuse an existing version image before
push. Build/scan the exact local images before uploading; no build-time credentials.
Use only the ephemeral workflow token and job-scoped packages:write. Keep source
Compose as default; add a release-image overlay preserving all project/state/security
settings and permitting bot-only use. Test anonymous pulls before claiming public
availability. GitHub package visibility may require a one-time owner setting.

- [x] Implement/test release gate and tag/metadata validation, then workflow.
- [x] Add registry Compose overlay and meaningful resolved-config verification;
  update version, changelog and aligned EN/RU registry/setup instructions.
- [x] Verify tests/context/integration/builds and source/history/image privacy;
  get independent review before publishing source or release tags.
- [x] Push source, wait for exact-commit CI, create new tag and publish images;
  verify anonymous registry availability, digests, labels and pullability.
- [x] Test pulled images using synthetic fixtures and QNAP, retain verified
  backups/config/project identities and old images, and document actual results.

No periodic tracker requests or extra real search tests. Prefer pull/inspect and
network-disabled QNAP probes over restarting live Jackett solely to test a registry.
Operator Telegram/search/download acceptance remains distinct from automated checks.

Source verification:659 tests and normal checks, actual registry/source Compose
equivalence across two versions, all three Docker command groups, native Jackett
password-protected API fixture, browser JS/TLS and wheel0.4.0 passed. All4 local
candidate images have0 Trivy vulnerability/secret records. Source/history/staged
Gitleaks and private-identifier comparison across reachable Git/source/all saved
regular layer files passed. Layer Gitleaks flagged4 public Python signing
fingerprints and libmagic's header-recognition database; exact upstream/package
equality and an independent review justified anchored, artifact-only exceptions.
No source-scanner exclusions were added. Final artifact scan passed. Independent
release-workflow review found no blockers.

Published sourcee342894 and immutablev0.4.0 after all4 exact main checks passed.
Publication attempt1 stopped before upload on the pre-existing intermittent
Chrome-not-reachable startup failure; a single failed-job rerun passed unchanged
checks and uploaded all4 images. No root-cause fix for that intermittent failure
is claimed. All4 manifests were already anonymously readable; no owner UI change
was needed. Their public digests match the uploaded versions and QNAP image
config/source/version/platform metadata. Downloaded tag source matches every file.
QNAP CLI/package probes passed, including all24 bot source/catalog hashes. Bot-only
registry rollout used a verified offline backup and digest pin, retaining durable
state/security and all3 companion containers/start times. Published GitHub release
includes a public digest manifest. No extra tracker warm-up/search was triggered.

One CodeQL cleartext-storage alert at the disposable test env sink was independently
reviewed as test-only. Automatic approval review rejected its administrative
dismissal without explicit owner permission; requested approval remains pending
and the alert stays open. Scanner rules were not changed. This is separate from
the completed image publication; real Telegram/search acceptance remains distinct.
