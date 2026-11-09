install:
	pip install -e ".[dev]"
audit:
	python scripts/inspect_dataset.py
build:
	python scripts/build_dataset.py
validate:
	python scripts/validate_dataset.py
api:
	uvicorn backend.main:app --reload
test:
	pytest
