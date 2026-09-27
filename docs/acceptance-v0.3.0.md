# v0.3.0 live acceptance

Recorded 2026-09-27 for public tag `v0.3.0`, commit
`18e940b1db491b7a87874585a65e48930dc9b965`, running on a Linux amd64 NAS.
The test used a dedicated Telegram bot, separate qBittorrent and separate state
and download storage. No private configuration is included in this repository.

## Operator-confirmed checks

- Start/help menus and English/Russian language selection.
- Live search, result selection and download controls.
- Health-screen display and refresh.
- Real Telegram completion-notification delivery.
- Monitoring recovery after a restart and no repeated delivered notification
  after a normal restart.

The operator reported successful manual acceptance. Agent checks separately
verified the native container build, service authentication, bilingual Telegram
command registration, state integrity and test isolation. Existing release CI
covers 539 offline tests plus container installation, outage, restart, rollback
and backup/restore scenarios.

## Scope and limitations

The hourly scheduler has automated coverage; its full one-hour interval was not
independently timed by the agent during this session. Normal restart acceptance
is not an exactly-once guarantee: a crash between sending and recording delivery
can still cause a repeated notification.

This acceptance applies to the tagged release on Linux amd64. ARM and later source
revisions require their own relevant verification. The temporary acceptance
containers were retired after testing; production deployment is a separate action.
