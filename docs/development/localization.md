# Localization boundaries

`i18n.tr` receives an explicit language; there is no global active language. Catalogs
must have matching keys/placeholders. `LanguageService` remembers Telegram detection
and explicit overrides in a separate database. Rendering resolves the owner again
on each update. Callback commands, torrent identities and state codes stay stable.

Health snapshots cache result codes and render per owner. New completion notices
use the current preference; durable pending payloads retain their saved text/buttons.
The narrowly scoped retired Plex suffix/button cleanup remains for compatibility.

The literal audit permits parser patterns for Russian release metadata, comments,
technical exceptions/logs, service names, units such as UTC, and the bilingual language
entry. All active Telegram prose and setup result messages use catalogs. Original
queries, torrent titles, paths and indexer names are never translated. Messages use
plain text rather than interpreting titles as markup.
