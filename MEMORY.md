# Project Memory

## Architecture

Watch subscriptions and pending notices use SQLite schema v1; health cards use a
separate sibling database. Search and dashboard action sessions are ephemeral.
Control handlers are sequential; slow search/add work runs once per user in background.

## Conventions

Verify additions by metainfo hash, not title/list position. Only completed data in a
seeding/upload state counts as finished. Notice delivery is at least once across crashes.
Test tokens and fixture IDs are deliberately synthetic. Preserve required attribution.

## Environment

Use Python 3.12 and the pinned development lock. Container tests create their own
internal networks/volumes; they never connect to a personal deployment.

## Language persistence

Preferences live in a separate `.preferences.sqlite3` sibling of the watch DB.
Detected language and explicit overrides are persisted separately. Resolve the owner
when rendering; never translate a queued notice again during delivery retries.
See `docs/development/localization.md` for rendering boundaries.

## Recovery

`backup_state.py` snapshots SQLite through its online API and rejects existing
destinations. Each DB is individually consistent; stop the bot for a quiet point
across all three. Ordinary code rollback retains current state. Snapshot restore
is separate and may replay notices. See bilingual backup guides for name mapping.

## Public release baseline

`v0.3.0` is the first public release; qBittorrent 5.x is required for controls
(the bundled tested version is 5.1.2). Release CI accepts Linux amd64 and uses only
synthetic Telegram transport. Real Telegram acceptance remains a separate check.
