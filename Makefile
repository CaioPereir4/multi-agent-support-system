.PHONY: install lint fmt test run hooks

install:
	uv sync --extra dev

hooks:
	uv run pre-commit install

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff check --fix .
	uv run ruff format .

test:
	uv run pytest

run:
	uv run uvicorn main:app --reload
