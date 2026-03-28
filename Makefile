.PHONY: check start-api start-dashboard test lint format

check: lint test

test:
	PYTHONPATH=src uv run pytest tests/

lint:
	uv run ruff check src/
	uv run mypy src/rca_extractor/core/

format:
	uv run ruff format src/

start-api:
	uv run uvicorn rca_extractor.api.main:app --reload

start-dashboard:
	uv run streamlit run src/rca_extractor/dashboard/app.py
