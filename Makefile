.PHONY: build dist test lint lint-fix format format-check clean

build:
	uv run --group dev pyinstaller ingram-check.spec --noconfirm

dist:
	uv build

test:
	uv run --group dev pytest

lint:
	uv run --group dev ruff check src/ tests/

lint-fix:
	uv run --group dev ruff check --fix src/ tests/

format:
	uv run --group dev ruff format src/ tests/

format-check:
	uv run --group dev ruff format --check src/ tests/

clean:
	rm -rf build/ dist/
