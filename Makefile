.PHONY: install lint fmt test run hooks docker-build docker-up docker-down docker-logs

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

docker-build:
	docker compose build

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f api
