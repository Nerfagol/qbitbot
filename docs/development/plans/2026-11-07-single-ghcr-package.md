# Single GHCR package

Owner selected one GHCR package with separate containers. Keep existing bot tags
unchanged and use component-prefixed companion tags in ghcr.io/nerfagol/qbitbot.
Copy the verified0.4.0 manifests without rebuilding; preserve digests, source
labels, published Git tags and live services. Future publication uses this layout.

- [x] Test and update canonical tag generation, overwrite checks, publisher,
  registry overlays and resolved-config checks.
- [x] Add a checksum-pinned, manual, main-only consolidation workflow. Verify
  exact current CI and the public0.4.0 source/digest lock; reject conflicting
  target tags, preserve existing equal tags and verify every copied digest.
- [ ] Verify/review source, publish it and run consolidation. Test anonymous
  access and QNAP pulls against the original manifest/config digests.
- [ ] Update current registry guides and add a consolidated public release asset.
  Retain original immutable source/tag/artifacts as historical evidence.
- [ ] Only after verified migration, request explicit approval before deleting
  the three old packages, because their existing public pull URLs will break.
  Cleanup must reject unknown legacy versions/tags or mismatching target digests.

No service restarts, tracker queries, production configuration or state changes.
Primary owns edits/records; an independent reviewer checks the stable diff.

Local verification:675 tests/lint/format/compile/dependency checks and actual
Compose settings-equivalence/context checks passed.29 focused registry tests cover
tag collisions, resumable equal-tag copies, copied-digest mismatch, owner-only
cleanup and unknown legacy data. Independent review found no blockers. Pinned
regctl0.11.7 was checksum verified and read-only checks confirmed every original
released digest and complete raw manifest graph. Source publication is phased:
publish the migration/publisher first while keeping existing registry overlays
valid; switch overlays/guides only after new tags are anonymously accessible.
