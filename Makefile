PYTHON ?= .venv/bin/python
RUFF ?= .venv/bin/ruff
DOCKER ?= docker
DOCKER_CONTEXT ?=
MODULES = backup_state.py preferences.py language_ui.py i18n.py settings.py setup_check.py watch_store.py monitoring.py downloads.py search_ui.py health.py
.PHONY: test known-bugs lint format check integration
test:
	$(PYTHON) -m pytest
known-bugs:
	$(PYTHON) -m pytest -m known_bug --runxfail
lint:
	$(RUFF) check tests integration $(MODULES)
	$(RUFF) format --check tests integration $(MODULES)
format:
	$(RUFF) format tests integration $(MODULES)
check: test lint
	$(PYTHON) -m py_compile tg_torrent_bot.py $(MODULES)
	$(PYTHON) -m pip --no-cache-dir check
integration:
	$(PYTHON) integration/run.py --docker $(DOCKER) $(if $(DOCKER_CONTEXT),--context $(DOCKER_CONTEXT),)

.PHONY: compose-check
compose-check:
	$(PYTHON) integration/compose_check.py --docker $(DOCKER) $(if $(DOCKER_CONTEXT),--context $(DOCKER_CONTEXT),)

.PHONY: integration-public
integration-public:
	$(PYTHON) integration/public_stack.py --docker $(DOCKER) $(if $(DOCKER_CONTEXT),--context $(DOCKER_CONTEXT),) --scenario all
