# Via http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

MSG ?= "Hello"

.PHONY: install-deps
install-deps: ## Install dependencies
	uv sync

.PHONY: run
run: ## Send prompt to AI agent (MSG="your prompt")
	uv run python main.py $(MSG)

.PHONY: clean
clean: ## Clean build artifacts and cache
	rm -rf .venv
	rm -rf build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

.PHONY: lint
lint: ## Run linters
	uv run ruff check .

.PHONY: format
format: ## Format code
	uv run ruff format .

.PHONY: install
install: install-cli

.PHONY: install-cli
install-cli: ## Install claude-pipe CLI
	@echo "Installing claude-pipe CLI..."
	uv pip install -e .
	@echo "Installation complete. You can now run 'claude-pipe' from anywhere."
