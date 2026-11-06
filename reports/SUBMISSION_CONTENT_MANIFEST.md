# SENSELINE Submission Content Manifest

Date: 2026-11-06 UTC. Source tree: branch `main` (see git log). Candidate artifact:
`dist/SENSELINE_SUBMISSION_CANDIDATE.zip` + `.sha256` (711 files, ~4.1 MB, < 50 MiB,
README at ZIP root, SHA-256 sidecar). No placeholder final ZIP is shipped: any previous
`dist/SENSELINE_FINAL_SUBMISSION.zip` placeholder build is preserved only under
`dist-archive/` for audit history. The final uploadable
`dist/SENSELINE_FINAL_SUBMISSION.zip` is created exclusively by
`scripts/finalize_submission.py --video-url "REAL_PUBLIC_VIDEO_FILE_URL"` after the owner
supplies a real public https URL and passes the `--mode final` extraction gate.

## Inclusion / exclusion rules

Built by `scripts/package_submission.py` (`archive_members`, `excluded`, `validate_members`):
excludes `.git`, `.venv`, `__pycache__`, `.pytest_cache`, `.DS_Store`, `__MACOSX`, `dist/`,
`dist-archive/` (historical sidecars are not submission material), nested `*.zip`,
`.pyc/.pyo/.log/.tmp/.bak`, credential-like names, `.env` (keeps
`.env.example` with empty values), symlinks refused. Requires README at ZIP root (flat, no
`SENSELINE/` outer dir), 8 task packages each with `task.md`, `input.schema.json`,
`output.schema.json`, `public_examples.json`, `solution.py`, plus `requirements.txt`,
`.env.example`, `Makefile`, `Dockerfile`, `graders/grade.py`, `oracle/compute.py`,
`harness/secure_execution.py`, `harness/candidate_runtime.py`, `scripts/run_experiment.py`,
`scripts/validate_submission.py`, `scripts/package_submission.py`,
`scripts/verify_release_archive.py`, `scripts/finalize_submission.py`,
`mutations/MUTATION_MANIFEST.json`, `tests/test_benchmark.py`, `tests/test_finalize.py`, `docs/` (METHODOLOGY,
RELATED_WORK, FAILURE_ANALYSIS, INDEPENDENT_REVIEW_PACKAGE),
and `results/` validation + canonical analysis. The video walkthrough script
(`docs/video_walkthrough_script.md`) and the slide deck (`presentation/`) stay in the
working repository but are excluded from the ZIP: they are delivery aids, not
evaluation material.

## What is included (and why)

- Eight task specifications + schemas + public examples + starters (evaluation contracts).
- Reference implementations (`reference/`) + independent oracle (`oracle/compute.py`) + grader
  (`graders/grade.py`) + hidden fixtures (`graders/hidden/S*.json`, 266 cases) for judge
  reproducibility (agent-confidential via task export, not repo-confidential).
- Scoring/grading logic, mutation controls (30), export + isolation + security scripts.
- Reproducible experiment evidence: `results/experiment_analysis.json` (91 trials:
  14 GENUINE / 58 TOOL_USE / 17 INFRA / 2 BUDGET_BREACH, phase-split, run_id-keyed pass@3/pass^3),
  `results/experiment_analysis.csv`, `results/aggregate.json` (raw 55-trial full-run record),
  `results/runs/`, `results/pilot/`, `results/pilot-history/`, `results/supplementary/`,
  `results/transcripts/`, per-trial `trial_index.json`/`score.json`/`transcript.json`/`workspace/solution.py`.
- Dependencies + setup (`requirements.txt`, `pyproject.toml`, `.env.example`, `Makefile`, `Dockerfile`).
- Documentation + reports (METHODOLOGY, FAILURE_ANALYSIS, review package,
  FINAL_RELEASE_AUDIT, FINAL_EXPERIMENT_ANALYSIS, FINAL_VALIDATION_REPORT,
  OWNER_REVIEW_REQUIRED pending, COST_AND_USAGE_DISCLOSURE, MODEL_COMPARISON, this manifest).
- Video field: README `Video walkthrough: VIDEO_URL_PENDING_OWNER_UPLOAD …` (candidate);
  finalize replaces it with the real public `https://` URL and rebuilds the final ZIP.

## What is excluded (and why)

- `.git`, `.venv`, caches, `__pycache__`, `.pytest_cache`, `.DS_Store`, `__MACOSX`, `dist/`,
  `dist-archive/` (audit history, not submission material), nested `*.zip`,
  `.pyc`, logs, temp files: development artifacts, not evaluation material.
- No actual API keys, passwords, private user info, or `.env` secrets (only `.env.example` with
  empty values; secret scan clean; transcripts redact credential material but retain
  operator-local absolute paths as provenance, disclosed).
- No unnecessary local logs or dev artifacts; no `FINAL_AUDIT_REPORT.md` (stale, excluded by rule).

## Verification

- `unzip -l` shows README at root, 8 task packages, 711 files, no outer directory.
- `testzip` CRC PASS, SHA-256 sidecar matches, size < 50 MiB.
- Fresh-extraction gate (`scripts/verify_release_archive.py --mode candidate --archive
  dist/SENSELINE_SUBMISSION_CANDIDATE.zip --checksum
  dist/SENSELINE_SUBMISSION_CANDIDATE.zip.sha256`) reinstalls deps, runs `pytest`
  (140 passed: 104 benchmark + 36 finalizer), `validate_submission.py
  --mode candidate` (266/266, 30/30), Docker security (12/12), Codex/OpenCode checks
  from the EXTRACTED candidate ZIP; reports TECHNICAL_PASS + PENDING_VIDEO.
- Final mode (`--mode final --archive dist/SENSELINE_FINAL_SUBMISSION.zip --checksum
  dist/SENSELINE_FINAL_SUBMISSION.zip.sha256`) rejects the placeholder; only
  `finalize_submission.py --video-url "REAL_PUBLIC_VIDEO_URL"` with a real public URL
  plus owner incognito confirmation yields a final PASS. The manifest count (711)
  exactly matches the actual archive member count.
