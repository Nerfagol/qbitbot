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
- [ ] Push source, wait for exact-commit CI, create new tag and publish images;
  verify anonymous registry availability, digests, labels and pullability.
- [ ] Test pulled images using synthetic fixtures and QNAP, retain verified
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
release-workflow review found no blockers. Hosted publication remains unverified.
