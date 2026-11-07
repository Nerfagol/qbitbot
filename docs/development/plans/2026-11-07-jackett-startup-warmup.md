# Restart-only Jackett warm-up

Owner selected complete search coverage and warm-up only on Jackett container
starts. No periodic requests, bot-startup warm-up, shortened searches or changes
to indexers, credentials, TLS or durable state.

Add a native s6 oneshot to the derived Jackett image, dependent on its existing
service readiness notification. Opt in through `JACKETT_WARMUP_ON_START=1` in
the bundled stack. Read the local API key privately, list configured indexers
locally and make one supported Test request per indexer with bounded time and
no helper retries. Failures finish best effort; health waits for completion,
then retains the normal Dashboard probe. Associate completion with PID1's start
time so a container restart cannot reuse an old marker. Bot-only restarts do
not rerun the hook. An internal Jackett process restart does not rerun the
container oneshot. Cookie expiry can still cause a later cold search.

- [x] Add offline behavior regressions; observe missing implementation fail.
- [x] Implement the startup hook, image inputs and bundled Compose health gate.
- [x] Verify zero idle/retry traffic and container restart behavior using only
  synthetic Docker fixtures; run normal checks and directory-context exclusions.
- [ ] Review, document results and deploy only after verification, preserving
  private configuration and backups. Never use repeated real tracker queries
  as a warm-up test.

Source review found no blockers after declaring host jq for offline tests.
645 tests and normal checks, Docker context exclusions, synthetic native-s6
startup/restart/idle tests, full public-stack acceptance/rollback and the current
Jackett image vulnerability scan passed. Deployment remains a separate next step.
