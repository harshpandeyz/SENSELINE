# SENSELINE release checklist

Evidence dates: 2026-11-06. Source validation and experiment results are retained in `results/`.

## Engineering and grading

- [x] Inspect the current source, task contracts, README, Makefile, experiment configuration, retained validation results, and prior-audit findings still available in the project.
- [x] S02/S08 unit-aware grading separates numeric accuracy, unit labels, physical equivalence, and missing-unit semantic integrity. Regressions cover wrong labels, missing units, incompatible dimensions, harmless extra fields, equivalent alternate units, and wrong values with missing units.
- [x] SCR counts corrupted genuine cases once over evaluated genuine cases; UAR uses non-ACCEPT S06/S08 genuine cases. Exact denominators, exclusions, and the GENUINE/TOOL_USE/INFRA eligibility rule are in `docs/METHODOLOGY.md` and `docs/FAILURE_ANALYSIS.md`.
- [x] S08 dimensions and processing order are explicit; 45 integration fixtures cover conversion, calibration, temperature compensation, uncertainty/covariance, boundaries, staleness, simultaneous defects, and valid end-to-end processing. Expected outputs were not changed to make implementations pass.
- [x] Independent oracle and reference solutions pass all 266 cases in Docker isolation. All 30 mutation controls are rejected for an intended failure dimension.

## Security and reproducibility

- [x] `make test`: 104 passed, zero skipped (2026-11-06; an 11-skip run during a dead Docker daemon was re-run green after restart).
- [x] `make validate`: test suite passed; 266/266 references, 30/30 mutations, eight task exports, and unit-integrity checks passed.
- [x] `make security-test`: Docker isolation tests 12/12 passed, zero skipped; Codex CLI 0.164.0-alpha.11.1 (reinstalled pinned) workspace and network checks passed; OpenCode 2.2.5 loaded task-local permissions and resolved shell/external-directory denies.
- [x] Candidate execution is Docker-isolated, network-disabled, non-root, read-only, resource-limited, and fail-closed. Each task export excludes hidden fixtures, graders, and reference solutions. Each trial starts in a new temporary workspace.
- [x] The OpenCode policy was resolved by the actual CLI, but dynamic denial of an OpenCode tool call was not exercised. Do not interpret policy resolution as a dynamic access test.
- [x] A secret scan of the tree and transcripts found no API keys or credentials (see reports/FINAL_RELEASE_AUDIT.md). Trial logs redact credential material.
- [x] Clean dependency installation and tests from the final ZIP are run by `make package` through `scripts/verify_release_archive.py`; that verifier also runs reference and security checks after fresh extraction.

## Model experiment and failure analysis

- [x] Inspected OpenCode 2.2.5 catalog (465 models), authenticated provider profiles, dedicated credential environment, local Ollama models, OpenRouter free-quota state, and paid-provider balances/limits.
- [x] Ran the 9-trial pilot to PILOT_COMPLETE with operator transcript review (owner review pending; see results/pilot/pilot_approval.json).
- [x] Ran the 72-design full experiment to 55 trials; halted by design with QUOTA_EXHAUSTED (free-tier quota, $0 cap intact). Preserved 24 pilot-history and 1 supplementary trial with phases labeled. 90 classified trials: 16 GENUINE, 58 TOOL_USE, 16 INFRA.
- [x] Genuine-only metrics computed (`results/experiment_analysis.json`): nemotron S01–S03 acc 0.977, SCR 0.0; pilot S08 corruption and UAR analyzed case-by-case; local-model tool-use boundary documented; no grader defects found.
- [ ] Nemotron S04–S08 block (17 trials) missing — free quota exhausted; rerun after 00:00 UTC reset or with funded credits (out of $0 scope).
- [ ] Paid frontier configurations not tested — no verifiable balance or provider hard limit; excluded honestly rather than fabricated.

## Documentation and submission

- [x] Root README contains scope, all eight tasks, architecture, metrics, install/run instructions, dependencies, actual experiment status/results, runtime/cost, references, AI disclosures, and an explicit PENDING video marker (no invented URL).
- [x] Methodology, related work, failure analysis (reconciled 89-trial evidence), five-minute walkthrough script, independent-review package, standalone slide deck, and reports/ (audit, experiment analysis, validation) are included and mutually consistent. No external reviewer or public video is claimed.
- [x] `make package` creates the final ZIP with README at the ZIP root and a SHA-256 sidecar; the archive verifier checks a fresh extraction, install, tests, validation, security, archive contents, and the 50 MiB limit.
- [ ] Publish the recording and replace the PENDING video marker with its public link (project-owner action).
- [ ] Complete owner review of pilot approval and this release (operator review recorded).

Release status: **READY_WITH_DISCLOSED_LIMITATIONS** — genuine model results, transcript-backed failure analysis, and full validation are delivered and reproducible; the missing nemotron S04–S08 block, the unpublished video, and pending owner review are disclosed blockers, not hidden gaps.
