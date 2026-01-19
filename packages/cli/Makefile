export POETRY_VIRTUALENVS_CREATE = false

.PHONY: setup install shell run-help build clean check-poetry

check-poetry:
	@if ! command -v $(POETRY) >/dev/null 2>&1; then \
		echo "Poetry not found. Install with 'pip install --user poetry'."; \
		exit 1; \
	fi

setup: check-poetry
	poetry install
	poetry build
	poetry -m pip install --force-reinstall dist/ndnp_openocr-*-py3-none-any.whl
	@echo "CLI ready. Run: 'ndnp_openocr --help' (current env) or 'poetry run ndnp_openocr --help'."

install: setup

shell: check-poetry
	poetry shell

run-help: check-poetry
	poetry run ndnp_openocr --help

build: check-poetry
	poetry build

clean:
	rm -rf dist *.egg-info
