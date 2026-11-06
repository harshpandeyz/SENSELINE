# SENSELINE Final Validation Report

Date: 2026-11-06 UTC. Environment: macOS, Python 3.11.16 venv, Docker Desktop 29.7.2,
pinned sandbox image `python:3.11.18-slim-bookworm@sha256:ef521de1…` present locally.

## Source-tree validation (executed)

| Check | Command | Result |
|---|---|---|
| Unit/integration tests | `.venv/bin/python -m pytest -q` | **104 passed, 0 skipped** |
| Reference + mutation validation | `.venv/bin/python scripts/validate_submission.py` | **PASS**: 266/266 references, 30/30 mutations rejected, 8 exports, unit-integrity PASS |
| Docker security | `.venv/bin/python scripts/run_docker_security_tests.py` | **PASS**: 12/12, 0 skipped |
| Agent workspace security | `.venv/bin/python scripts/verify_agent_security.py` | **PASS** (codex-cli 0.164.0-alpha.11.1, reinstalled pinned) |
| OpenCode permissions | `.venv/bin/python scripts/verify_opencode_permissions.py` | **CLI_CONFIG_RESOLVED** (opencode v2.2.5; policy resolution only, no dynamic denial claimed) |
| Experiment analysis | `.venv/bin/python scripts/analyze_results.py` | 90 trials classified; canonical JSON + CSV written |
| Aggregate (raw record) | `.venv/bin/python -m harness.aggregate --results results` | 55 full trials, PARTIAL (nemotron S04–S08 absent on quota) |

Note: one pytest run showed 11 docker-integration skips while the Docker daemon was down;
the daemon was restarted, the image re-verified, and the suite re-run green (104/104).
The skip episode is recorded here, not hidden.

## Grader and task audit (Phase F)

- S01–S08 contracts, schemas, and expected outputs reviewed against `tasks/`,
  `oracle/compute.py`, and `reference/`; no task or tolerance was altered for any model.
- The grader cannot reward universal rejection: correctness requires exact expected
  dispositions and values; wrong-unit-marked-valid outputs count as physical corruption
  (verified by mutation controls), while harmless extra fields stay schema-contract
  violations (verified by `S08_extra_schema_field`, SCR numerator 0).
- Hidden fixtures `graders/hidden/S*.json` ship in the repo/ZIP so judges can reproduce
  grading deterministically. They are confidential only relative to the evaluated agent
  (task export copies 5 visible files + AGENT_README; hidden material is never mounted
  into candidate containers). They are not secret from anyone inspecting the ZIP or repo.

## Candidate isolation audit (Phase G)

- Trial candidates execute exclusively via `DockerCandidate` (`harness/secure_execution.py`);
  host-Python execution occurs only for trusted references/mutations during validation.
- `harness/run_trial.py:492,507` constructs the Docker facade for every trial; grading
  raises (fail-closed) if Docker/the pinned image is unavailable — no host fallback exists.
- Containers: `--network=none`, non-root UID 65534, dropped capabilities,
  no-new-privileges, read-only mounts/rootfs, tmpfs limits, CPU/memory/PID/ulimit caps,
  bounded output, wall timeout. Candidate mounts: solution.py + runner only (read-only).
- Candidate containers receive no agent credentials or host environment; agent HOME/config
  are task-local; host auth files are never copied.
- Secret scan (API-key patterns across code/docs/results, excluding allowlists/templates):
  clean. Trial transcripts redact credential material; they retain operator-local absolute
  paths (provenance, no credentials) — disclosed, not sanitized, to preserve raw evidence.
- `.env` files: none in repo or archive; only `.env.example` with empty values.

## Python dependencies

Pinned in `requirements.txt` (`jsonschema 4.23.0`, `pytest 8.3.5`, etc.), installed in a
fresh `python3.11` venv for every validation gate, including the archive-extraction gate below.

## Archive gate (Phase I)

The release artifact is verified by independent extraction (see packaging log):
`dist/SENSELINE_FINAL_SUBMISSION.zip` (4,096,664 bytes, SHA-256
`e12958522955234d18477899f28a348023aec18cbad01aece8cdea2ed4255ac7`, 713 files)
+ `.sha256` sidecar — fresh-directory extraction, clean dependency install, `pytest`,
`validate_submission.py`, Docker security, and Codex/OpenCode checks re-executed from the
extracted copy with PASS (782.6 s); video status PENDING_OWNER_ACTION is recorded in
`results/archive_validation.json` as the release blocker. README-at-root, 8 task packages,
50 MB limit, and prohibited-file scan all enforced by `scripts/verify_release_archive.py`.
