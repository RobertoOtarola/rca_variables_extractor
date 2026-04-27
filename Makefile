.PHONY: install check test lint format clean start-api start-dashboard scrape

install:
	uv sync --all-extras --dev

check: lint test

test:
	uv run pytest tests/

lint:
	uv run ruff check src/
	uv run mypy src/rca_extractor/core/ src/rca_extractor/post_processing/ src/rca_extractor/lca/

format:
	uv run ruff format src/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -f .coverage

scrape:
	@if [ -z "$(ID)" ]; then \
		echo "Uso: make scrape ID=7021124"; \
	else \
		uv run python -m rca_extractor.tools.rca_scraper --id $(ID); \
	fi

start-api:
	uv run uvicorn rca_extractor.api.main:app --reload

start-dashboard:
	uv run streamlit run src/rca_extractor/dashboard/app.py
