# English and Russian Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Translate the entire bot interface while preserving reliable controls and restart-safe notifications.

**Architecture:** Pure catalogs render explicit language arguments. A separate preference database remembers detected language and user overrides; handlers, owned cards and background tasks resolve language through one service. Durable notices keep already-queued text unchanged.

**Tech Stack:** Python 3.12, JSON catalogs, SQLite, existing python-telegram-bot 21.11.1 API, pytest.

**Spec:** [Approved design](../specs/2026-09-27-public-release-design.md); prerequisite: [packaging plan](2026-09-27-public-packaging.md).

## Global Constraints

- English is the fallback for unsupported languages or missing preference information.
- Keep callback payloads, commands, torrent identities and stored status codes language-neutral.
- Pass language explicitly through rendering boundaries so simultaneous users cannot change each other's text.
- Preserve torrent titles, paths and indexer names verbatim and escape them safely.
- Keep watch schema and existing pending-notice compatibility intact.
- Once a notice is queued durably, its saved text remains unchanged during retries, even if the language preference changes.
- Historical sent messages are not bulk-rewritten after switching language.
- Preserve owner guards, allowlist checks, sequential controls and metadata-based addition identity.

## Review Focus

1. A Russian user must retain automatic language after restart even without choosing manually: task 2 persists detected language separately from override.
2. Two users in a group must not change each other's cards or preferences: tasks 2–5 test ownership and concurrent rendering.
3. Switching language during an active search must retain valid target guards and consume-once behavior: task 3 tests stale/current tokens.
4. A queued Russian notice must not become English on retry: task 5 tests byte-identical text/markup after restart.
5. Long Unicode names and Russian number forms must remain readable within Telegram limits: tasks 1, 3 and 4 test boundary values and unchanged titles.

## Files and responsibilities

- Create `i18n.py`, `locales/en.json`, `locales/ru.json`: pure translation/plural selection.
- Create `preferences.py`: durable per-user settings and language resolution.
- Create `language_ui.py`: owner-bound language chooser and handlers.
- Modify existing renderers in root, `search_ui.py`, `downloads.py`, `health.py`, `monitoring.py`; preserve algorithms and controller structure.
- Modify `setup_check.py` for selectable diagnostic language; `Dockerfile`/`.dockerignore` to include new modules/catalogs.
- Create `tests/test_i18n.py`, `test_preferences.py`, `test_language_ui.py`, `test_search_languages.py`, `test_download_languages.py`, `test_monitoring_languages.py` under `tests/`.

## Task 1: Catalog and plural contract

**Files:** `i18n.py`, catalogs, `tests/test_i18n.py`, Docker build inputs.

**Interfaces:** `Language = Literal['en', 'ru']`; `normalize_language(code: str | None) -> Language`; `plural_form(language: Language, count: int) -> str`; `tr(key: str, language: Language, *, count: int | None = None, **values: object) -> str`. Catalog leaves are strings or plural dictionaries (`one/other` for English, `one/few/many` for Russian). Counts are nonnegative integers.

- [ ] Add failing assertions: `normalize_language('ru-RU') == 'ru'`, `normalize_language(None) == 'en'`, `normalize_language('de') == 'en'`; plural forms for 0, 1, 2, 5, 11, 12, 14, 21, 22, 25, 101, 111. Assert both catalogs have matching message keys and format-field sets. Run `pytest tests/test_i18n.py -q`; expect missing-module/interface failures.

  ```python
  assert [plural_form('ru', n) for n in (1, 2, 5, 11, 21, 22, 111)] == [
      'one', 'few', 'many', 'many', 'one', 'few', 'many'
  ]
  assert normalize_language('ru-RU') == 'ru'
  assert normalize_language(None) == normalize_language('de') == 'en'
  ```
- [ ] Implement pure catalog loading/formatting without process-global active language. A missing Russian key falls back to English; an unknown key missing in both catalogs raises `KeyError`. Test malformed placeholders explicitly; CI rejects incomplete catalogs despite runtime fallback. Locale selection never changes input values.
- [ ] Add complete namespace inventory from existing renderers: `menu`, `help`, `language`, `search`, `release`, `download`, `progress`, `health`, `notice`, `error`, `setup`, `units`. Populate existing copy as each owning task migrates it. Preserve practical labels/emoji and avoid machine-translating release titles.
- [ ] Test formatting with braces, HTML-like tags, ampersands and emoji in user strings; use plain-text messages (`parse_mode=None`) where existing flows do. Do not re-interpret inserted values as format strings. Add modules/catalogs to the allowlisted image context.
- [ ] Run `pytest tests/test_i18n.py -q` and `make check`; commit `feat: add English and Russian translation catalogs`.

## Task 2: Persistent preference and language chooser

**Files:** `preferences.py`, `language_ui.py`, root lifecycle/menu, preference/UI tests and updated menu fixtures.

**Interfaces:** `PreferenceStore(path: Path)`, methods `get(user_id: int) -> dict | None`, `remember(user_id: int, detected: Language) -> None`, `set_override(user_id: int, language: Language) -> None`, `close() -> None`. Rows have `user_id`, `detected`, nullable `override`; writes are transactional. `LanguageService(store)` exposes `for_user(user_id: int | None, telegram_code: str | None = None) -> Language` and `set_for_user(user_id: int, language: Language) -> None`. `LanguagePicker(service, allowed)` exposes async `open(update, context)` and `callback(update, context)`. Root exposes `language_for_update(update, context) -> Language`, resolving the service in `context.application.bot_data`. Existing API adapters receive `language_for_user=service.for_user`; root factories become `downloads_dashboard(language_for_user)` and `search_browser(language_for_user)`.

- [ ] Add failing tests for Russian autodetection surviving a reopened DB, missing language not erasing detection, explicit override winning over later Telegram changes, and users remaining independent. Assert preference DB path is `Path(WATCH_DB_PATH).with_suffix('.preferences.sqlite3')`, modes 700/600 for newly created directory/file, and existing watch DB bytes/schema unchanged. Run preference tests; confirm expected failures.
- [ ] Implement preference store/service; close only after background tasks stop. Initialize before menus/watch restoration. In normal handler dispatch, remember present Telegram codes for allowlisted users only. Store unavailable Telegram language as English on first contact, but never reset an existing detection from a missing code. Wire `language_for_user` into root's dashboard/search/health/monitoring API objects; test missing user IDs fall back to English without creating rows.
- [ ] Keep the service in `application.bot_data['languages']` and bind its `for_user` method into existing API adapters. Extend `WatchManager`'s owned `SimpleNamespace` context with `language_for_user=api.language_for_user`; the root watcher calls `context.language_for_user(context.user_id)`. Do not introduce a mutable global current language. Tests supply their own service/adapters.
- [ ] Add chooser tests: `/language` and visible `Language / Язык` entry, `English` and `Русский` buttons, success confirmation in selected language, and no write for revoked users, other owners, mismatched chat/message, expired or replayed callbacks. Implement random `lang:` callback tokens stored in `context.user_data` with 15-minute expiry and consume-before-await ordering. Register before the catch-all search callback handler.
- [ ] Translate root start/help/search prompts and command descriptions; register default English and Russian menus using `language_code`. For a private-chat override, register the selected descriptions at chat scope for `''`, `'en'` and `'ru'` so Telegram-language precedence cannot undo the explicit choice; keep group menus language-specific globally. Menu API errors must not undo saved preferences or block watch restoration. Restore private-menu choices for persisted overrides on startup.
- [ ] Run `pytest tests/test_preferences.py tests/test_language_ui.py tests/test_menu.py -q` and `make check`. Adapt legacy test API fixtures to explicitly request Russian where asserting historical Russian copy; add independent tests proving real default English. Commit `feat: remember language preferences and expose language selection`.

## Task 3: Search and release-detail translation

**Files:** `search_ui.py`, root search/add handlers, `monitoring.py` busy prompts, catalogs, `tests/test_search_languages.py` and affected search tests.

**Interfaces:** Extend `search_notice(results, *, language: Language = 'en')`, `availability(item, *, language='en')`, `quality_label(item, *, language='en')`, `release_details(value, *, language='en')`. Extend `SearchBrowser.metadata(item, *, preview=False, language='en')`. Existing parameter dictionaries remain untyped at their current API boundary. Session `user` remains the identity source; `api.language_for_user(session['user'])` supplies each render's language. `SearchJobs` receives a language resolver with English fallback, without changing its one-job-per-user contract.

- [ ] Add parametrized EN/RU tests covering searching, full/partial/failed/empty results, retry, numbered list, sort/filter menus, previews, original-title pages, explicit add and added/already-present/uncertain feedback. Assert translated labels plus unchanged action/target values. Run `pytest tests/test_search_languages.py -q`; identify untranslated paths as failures.
- [ ] Move rendering strings into catalogs and pass language explicitly. Keep ranking, minimum viable source threshold, filter values and title parsing unchanged. Translate recognized labels only; preserve original title and unrecognized metadata. Translate root addition/subscription failures and busy responses too.
- [ ] Add tests switching language between list/preview/confirmation, overlapping users with opposite languages, 1400-character original-name pages and Unicode titles. Assert exactly one add for consumed confirmation, expired/foreign buttons remain rejected, long text remains within Telegram limits, and user query text is never translated.
- [ ] Run all `tests/test_search*.py`, release-detail, add-identity and background-job tests plus `make check`. Commit `feat: localize search filters and release selection`.

## Task 4: Downloads and shared progress translation

**Files:** `downloads.py`, root status/progress/navigation helpers, catalogs, `tests/test_download_languages.py` and affected download tests.

**Interfaces:** Add keyword-only `language: Language = 'en'` to `waiting_guidance`, `download_status`, `remaining_time`, `download_progress`, `download_location` and root `format_download_progress`; retain other arguments. Dashboard methods resolve language from their owner on each render. `torrent_navigation(..., label=None, language='en')` selects a translated default label; callback content remains unchanged.

- [ ] Add failing EN/RU assertions for numbered list (eight entries), groups/counts, details, pause/resume, named delete-with-files confirmation, empty library, stale views and API errors. Cover metadata/checking/paused/queued/error/completed states and unknown ETA. Run targeted language tests and confirm relevant copy failures.
- [ ] Translate display strings/units and `/status`; retain state classification, strict completion, selected-size accounting, progress bar and UTC snapshot semantics. Stable group keys stay separate from translated labels. Keep file/path values verbatim.
- [ ] Test language switching between selecting a torrent and confirming deletion: guard/target identity must still match and one mutation occurs. Test another owner in the same group cannot act. Check long Unicode names, counts at plural boundaries, vanished torrents and recoverable errors in both languages.
- [ ] Run all download tests, completion-action tests and `make check`; commit `feat: localize downloads and progress controls`.

## Task 5: Background cards, completion notices and diagnostic language

**Files:** `health.py`, `monitoring.py`, root watcher/lifecycle, `setup_check.py`, catalogs, `tests/test_monitoring_languages.py`, existing health/persistence/error tests.

**Interfaces:** `HealthManager.text(user_id: int) -> str`, `markup(token: str, user_id: int)`; cached probe snapshots store stable result codes, not translated strings. Watcher calls `context.language_for_user(context.user_id)` every cycle; existing `WatchStore.pending` remains unchanged. `setup_check.main` accepts `--language en|ru` (default `en`), translating `CheckResult.message_key` from plan 1.

- [ ] Write failing tests for two differently owned health cards sharing one service sample, language change before refresh, restored cards/watches using persisted preferences, and expired/revoked ownership remaining blocked. Run `pytest tests/test_monitoring_languages.py -q`; verify failures correspond to untranslated owner-aware rendering.
- [ ] Translate health text/buttons, outage/recovery/missing messages, progress and first-created completion notices. Keep hourly cycles and the 30-second sample cache unchanged. Store probe outcome codes; translate separately for each card. Re-resolve language before composing a new notice; allow an already-queued notice to stay in its original language.
- [ ] Test crash/restart with an already-pending Russian notice followed by an English preference: retry text and button metadata match the queued payload exactly. Old v1 watch rows and optional notice metadata still restore; no preference migration rewrites them. Existing legacy notice-cleanup compatibility remains narrowly scoped. Verify shutdown cancels watchers before closing preferences.
- [ ] Translate safe setup diagnostics and root startup errors; preserve machine-readable keys for tests. Inventory remaining human-facing literals across all six modules and setup code. Permit only documented legacy compatibility literals, parser patterns and technical diagnostics outside catalogs; require translations for every active user-facing path.
- [ ] Run `make check`, rebuild the bot image and run isolated integration checks. Expected: both languages covered, strict regression suite passes, catalogs are bundled, no live Telegram or tracker traffic. Commit `feat: localize persistent health and completion notifications`.

## Milestone acceptance

Both languages work through the full bot, including background delivery and restart. Record actual checks in the public progress log. Proceed to plan 3 for clean-install and publication acceptance; do not treat translation coverage as deployment verification.

## Reference

[Telegram command scopes and language codes](https://core.telegram.org/bots/api#setmycommands) define menu registration; verify against the pinned Python library during implementation.
