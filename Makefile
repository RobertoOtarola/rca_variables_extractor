.PHONY: check start-api start-dashboard test lint format

check: lint test

test:
	PYTHONPATH=src pytest tests/

lint:
	ruff check src/
	mypy src/rca_extractor/core/

format:
	ruff format src/

start-api:
	uvicorn rca_extractor.api.main:app --reload

start-dashboard:
	streamlit run src/rca_extractor/dashboard/app.py
