PYTHON ?= python3

.PHONY: validate conformance boundary test build check clean

validate:
	$(PYTHON) -m evals.cli validate
	$(PYTHON) -m eval_runner.bench validate

conformance:
	$(PYTHON) -m evals.cli conformance

boundary:
	$(PYTHON) scripts/export-eval-runner.py --check

test:
	$(PYTHON) -m pytest

build:
	$(PYTHON) -m build

check:
	$(PYTHON) -m compileall -q evals eval_runner tests
	$(MAKE) validate
	$(MAKE) conformance
	$(MAKE) boundary
	$(MAKE) test
	$(MAKE) build

clean:
	$(PYTHON) -c 'import shutil; [shutil.rmtree(path, ignore_errors=True) for path in ("build", "dist", ".pytest_cache")]; [shutil.rmtree(path, ignore_errors=True) for path in __import__("pathlib").Path(".").glob("*.egg-info")]'
