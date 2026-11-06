PYTHON := .venv/bin/python
RUFF := .venv/bin/ruff
MYPY := .venv/bin/mypy
PYTEST := .venv/bin/pytest

.PHONY: lint format typecheck test test-unit test-integration coverage all

lint:
	$(RUFF) check .

format:
	$(RUFF) format .

format-check:
	$(RUFF) format --check .

typecheck:
	$(MYPY) agent/ tools/ api/

test:
	$(PYTEST) -q

test-unit:
	$(PYTEST) tests/test_loop.py tests/test_tools.py tests/test_db.py tests/test_config.py tests/test_providers.py tests/test_security.py tests/test_api.py -q

test-integration:
	$(PYTEST) tests/test_integration.py -q --no-cov

coverage:
	$(PYTEST) --cov=agent --cov=tools --cov=api --cov-report=term-missing

all: lint format-check typecheck test
	@echo "All checks passed."