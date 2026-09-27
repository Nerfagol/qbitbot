# Source inventory

Independent source export; no donor Git history or deployment data is included.

| Path | Purpose / status |
| --- | --- |
| `tg_torrent_bot.py` | Reviewed runtime/build input |
| `watch_store.py` | Reviewed runtime/build input |
| `monitoring.py` | Reviewed runtime/build input |
| `downloads.py` | Reviewed runtime/build input |
| `search_ui.py` | Reviewed runtime/build input |
| `health.py` | Reviewed runtime/build input |
| `Dockerfile` | Reviewed runtime/build input |
| `requirements.lock` | Reviewed runtime/build input |
| `requirements-dev.lock` | Reviewed runtime/build input |
| `pyproject.toml` | Reviewed runtime/build input |
| `pytest.ini` | Reviewed runtime/build input |
| `.gitattributes` | Reviewed runtime/build input |
| `.dockerignore` | Reviewed runtime/build input |
| `integration/run.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `integration/probe.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/__init__.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/conftest.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/helpers.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_add_identity.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_background_jobs.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_behavior.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_completion_actions.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_download_health.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_download_links.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_download_overview.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_download_progress.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_download_selection.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_downloads.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_error_recovery.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_health.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_known_bugs.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_menu.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_persistence.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_release_details.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_reliability_edges.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_search_availability.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_search_filters.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_search_recommendations.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_search_ui.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |
| `tests/test_verification_cleanup.py` | Synthetic behavior/integration test; reviewed and identifying fixture names generalized |

Private manual acceptance launchers and their setup tests are omitted. Their local
fixture/live-mode coverage is replaced by the public Compose setup and fresh-stack
verification tasks; no personal acceptance configuration is exported.

`integration/fixtures.py` retains only the pure `bencode` and `sample` generators
needed by metadata-identity tests. No manual setup/service code is included.
