VENV = .venv
PY = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip

.PHONY: setup scan run bot clean

setup: ## Create venv and install dependencies
	python3 -m venv $(VENV)
	$(PIP) install -e ".[dev]"

scan: ## One-shot scan across all projects
	$(PY) -m cyrano scan

run: ## Start scheduler + Telegram bot (production)
	$(PY) -m cyrano run

bot: ## Start Telegram bot only (test approval flow)
	$(PY) -m cyrano bot

clean: ## Remove venv
	rm -rf $(VENV)

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
