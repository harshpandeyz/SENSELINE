PYTHON ?= python3.11
VENV := .venv
VPY := $(VENV)/bin/python
EXPERIMENT_MATRIX ?= configs/experiment_matrix.template.json
EXPERIMENT_EXECUTE ?= 0
EXPERIMENT_EXECUTE_ARG = $(if $(filter 1 true yes,$(EXPERIMENT_EXECUTE)),--execute,)

.PHONY: setup test security-test opencode-verify validate experiment-pilot experiment-full package aggregate clean

setup:
	$(PYTHON) -m venv $(VENV)
	$(VPY) -m pip install --disable-pip-version-check -r requirements.txt

test:
	$(VPY) -m pytest -q

security-test:
	$(VPY) scripts/run_docker_security_tests.py
	$(VPY) scripts/verify_agent_security.py
	$(VPY) scripts/verify_opencode_permissions.py

opencode-verify:
	$(VPY) scripts/verify_opencode_permissions.py

validate:
	$(VPY) -m pytest -q
	$(VPY) scripts/validate_submission.py

experiment-pilot:
	$(VPY) scripts/run_experiment.py --matrix $(EXPERIMENT_MATRIX) --mode pilot $(EXPERIMENT_EXECUTE_ARG)

experiment-full:
	$(VPY) scripts/run_experiment.py --matrix $(EXPERIMENT_MATRIX) --mode full $(EXPERIMENT_EXECUTE_ARG)

package:
	$(VPY) scripts/package_submission.py
	$(VPY) scripts/verify_release_archive.py

package-final:
	SENSELINE_ARCHIVE_NAME=SENSELINE_FINAL_SUBMISSION.zip $(VPY) scripts/package_submission.py
	SENSELINE_ARCHIVE_NAME=SENSELINE_FINAL_SUBMISSION.zip $(VPY) scripts/verify_release_archive.py

aggregate:
	$(VPY) -m harness.aggregate --results results

clean:
	rm -rf $(VENV) .pytest_cache dist build
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
