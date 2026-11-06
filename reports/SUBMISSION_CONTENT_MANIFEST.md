# SENSELINE Submission Content Manifest

Date: 2026-11-06 UTC. Source tree: branch `main` (see git log). Candidate artifact:
`dist/SENSELINE_SUBMISSION_CANDIDATE.zip` + `.sha256` (716 files, ~4.1 MB, < 50 MiB,
README at ZIP root, SHA-256 sidecar). Final uploadable `dist/SENSELINE_FINAL_SUBMISSION.zip`
is rebuilt by `scripts/finalize_submission.py` after the owner supplies the real public URL
(current final ZIP is a placeholder build with identical technical content; final validation
rejects it until the URL is inserted).

## Inclusion / exclusion rules

Built by `scripts/package_submission.py` (`archive_members`, `excluded`, `validate_members`):
excludes `.git`, `.venv`, `__pycache__`, `.pytest_cache`, `.DS_Store`, `__MACOSX`, `dist/*.zip`
(nested archives), `.pyc/.pyo/.log/.tmp/.bak`, credential-like names, `.env` (keeps
`.env.example` with empty values), symlinks refused. Requires README at ZIP root (flat, no
`SENSELINE/` outer dir), 8 task packages each with `task.md`, `input.schema.json`,
`output.schema.json`, `public_examples.json`, `solution.py`, plus `requirements.txt`,
`.env.example`, `Makefile`, `Dockerfile`, `graders/grade.py`, `oracle/compute.py`,
`harness/secure_execution.py`, `harness/candidate_runtime.py`, `scripts/run_experiment.py`,
`scripts/validate_submission.py`, `scripts/package_submission.py`,
`scripts/verify_release_archive.py`, `scripts/finalize_submission.py`,
`mutations/MUTATION_MANIFEST.json`, `tests/test_benchmark.py`, `docs/` (METHODOLOGY,
RELATED_WORK, FAILURE_ANALYSIS, video_walkthrough_script, INDEPENDENT_REVIEW_PACKAGE),
`presentation/SENSELINE_walkthrough.html`, and `results/` validation + canonical analysis.

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
- Documentation + reports (METHODOLOGY, FAILURE_ANALYSIS, video script, review package, slides,
  FINAL_RELEASE_AUDIT, FINAL_EXPERIMENT_ANALYSIS, FINAL_VALIDATION_REPORT,
  OWNER_REVIEW_REQUIRED pending, COST_AND_USAGE_DISCLOSURE, MODEL_COMPARISON, this manifest).
- Video field: README `Video walkthrough: VIDEO_URL_PENDING_OWNER_RECORDING …` (candidate);
  finalize replaces it with the real public `https://` URL and rebuilds the final ZIP.

## What is excluded (and why)

- `.git`, `.venv`, caches, `__pycache__`, `.pytest_cache`, `.DS_Store`, `__MACOSX`, `dist/*.zip`
  (no nested archives), `.pyc`, logs, temp files: development artifacts, not evaluation material.
- No actual API keys, passwords, private user info, or `.env` secrets (only `.env.example` with
  empty values; secret scan clean; transcripts redact credential material but retain
  operator-local absolute paths as provenance, disclosed).
- No unnecessary local logs or dev artifacts; no `FINAL_AUDIT_REPORT.md` (stale, excluded by rule).

## Verification

- `unzip -l` shows README at root, 8 task packages, 716 files, no outer directory.
- `testzip` CRC PASS, SHA-256 sidecar matches, size < 50 MiB.
- Fresh-extraction gate (`scripts/verify_release_archive.py --mode candidate`) reinstalls deps,
  runs `pytest` (104 passed), `validate_submission.py --mode candidate` (266/266, 30/30),
  Docker security (12/12), Codex/OpenCode checks; reports TECHNICAL_PASS + PENDING_VIDEO.
- Final mode (`--mode final`) rejects the placeholder; only `finalize_submission.py` with a real
  public URL yields a final PASS.
