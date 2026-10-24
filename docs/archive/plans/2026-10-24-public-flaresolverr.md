# Public FlareSolverr packaging plan

> Historical record: paths and commands describe their original revision. Use the
> [current guides](../../README.md) for the current source layout.

Goal: make the already tested hardened optional FlareSolverr installation
reproducible from public source, with no private configuration or deployment data.

- Copy reviewed digest-pinned Dockerfile and asserted strict-TLS patches into
  docker/, preserving application3.5.2 and tested Alpine/runtime inputs.
- Add an optional bundled-stack Compose overlay: Jackett-only solver network,
  no published API port, UID1000/read-only/caps/NNP and tested resource limits.
- Extend recurring image scans and add synthetic internal-network browser/TLS
  smoke verification. No real tracker accounts or Telegram poller in tests.
- Document generic setup, dated scan scope and no-sandbox/API limitations.
- Run make check, resolve Compose, rebuild/rescan and run browser smoke.
  Preserve existing uncommitted work; do not commit, push or deploy.
