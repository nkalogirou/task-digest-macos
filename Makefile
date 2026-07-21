.PHONY: setup test check install uninstall clean

setup:
	./scripts/setup_local.sh

test:
	.venv/bin/python -m pytest -q

check: test
	.venv/bin/python scripts/check_public_repo.py

install:
	./scripts/install_all.sh

uninstall:
	./scripts/uninstall_all.sh

clean:
	rm -rf build dist .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -name '*.pyc' -delete
