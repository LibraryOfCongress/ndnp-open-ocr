export POETRY_VIRTUALENVS_CREATE = false

.PHONY: install clean check-poetry

check-poetry:
	@if ! command -v poetry >/dev/null 2>&1; then \
		echo "Poetry not found. See https://python-poetry.org/docs/#installation"; \
		exit 1; \
	fi

install: check-poetry
	poetry install
	poetry build
	pip install --force-reinstall dist/ndnp_openocr-*-py3-none-any.whl
	@echo "CLI ready. Run: ndnp_openocr --help"