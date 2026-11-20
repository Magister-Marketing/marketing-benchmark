PYTHON ?= python3

.PHONY: validate conformance boundary test build check clean bench-model

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

# Benchmark one model and put it on the results site; see scripts/bench-model.py
# and the README. Nothing is spent without confirm=SPEND; dry_run=1 prints the
# plan and the estimate; export=<run folder> exports a graded run and drafts
# its tweet without spending.
bench-model:
	@$(PYTHON) scripts/bench-model.py $(if $(web),--web "$(web)") \
		$(if $(model),--model "$(model)") \
		$(if $(filter 1,$(plain)),--plain) \
		$(if $(reps),--reps $(reps)) \
		$(if $(filter 1,$(inside)),--inside) \
		$(if $(magister),--magister "$(magister)") \
		$(if $(lane),--lane "$(lane)") \
		$(if $(env_file),--env-file "$(env_file)") \
		$(if $(like),--like "$(like)") \
		$(if $(export),--export "$(export)") \
		$(if $(ran_on),--ran-on "$(ran_on)") \
		$(if $(filter 1,$(dry_run)),--dry-run) \
		$(if $(confirm),--confirm "$(confirm)")
