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
