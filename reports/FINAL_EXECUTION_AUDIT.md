# FINAL_EXECUTION_AUDIT (internal execution log + project state)

Date: 2026-11-06 UTC. This file is the Phase-A execution audit: what was inspected, what was
found, what was fixed, and what remains. It is superseded as a release statement by
`reports/FINAL_RELEASE_AUDIT.md`; it is retained as the work log.

## Inspection performed

- Git: branch `main`, remote `https://github.com/harshpandeyz/SENSELINE`; merged and pushed (no force-push).
- Tasks S01–S08, oracle, references, grader, hidden fixtures, harness, Docker isolation, matrix, transcripts, analyses, budgets, README/methodology/failure-analysis/checklist/approvals, packaging scripts, presentation, prior ZIP+checksum: all read before modification.
- Prior aggregate reports were re-derived from raw trial records, never trusted.

## Defects found and fixed

1. Harness setup-block defect (zero-cost credentialed configs rejected) — fixed, regression-tested.
2. Paid-budget gate catching zero-cost trials — fixed (explicit exclusion).
3. No-retry / abort-on-first-flake behavior — replaced with bounded zero-cost retry + continue-with-evidence rule (paid path unchanged).
4. Token budget 60k too low for reasoning models (breach at 82740) — raised to uniform 120k; truncated trial preserved + excluded.
5. Matrix editing error (nemotron left at 60k) — corrected; one truncated trial excluded with evidence preserved.
6. Validator placeholder rule (required literal placeholder) — now accepts real URL or explicit PENDING; rejects placeholders; PENDING recorded as release blocker.
7. Archive name fixed to `SENSELINE_submission.zip` default with `SENSELINE_FINAL_SUBMISSION.zip` override + `package-final` target.
8. Analysis: no eligibility classification — added INFRA/TOOL_USE/GENUINE/BUDGET_BREACH generator + phase split + supplementary/history imports.
9. Docs claiming NOT RUN / wrong counts (17 GENUINE, UAR 2/23 conflation, untraceable 32/45) — reconciled to raw records (14/58/17/2 of 91; per-run UARs).
10. Missing deliverables created: `scripts/analyze_results.py`, `configs/experiment_matrix.json`, `results/free_model_availability.json`, reports/ (5 files), `results/pilot-history/`, `results/supplementary/`.

## Environment incidents (recorded, not hidden)

- Docker daemon down during one pytest run (11 docker-integration skips) — restarted, image re-verified, suite green (104/104).
- Host memory pressure (16 GB) correlated with Ollama no-route flakes — mitigated by single-resident-model scheduling.
- `codex` CLI missing from PATH — reinstalled pinned 0.164.0-alpha.11.1; checks pass.
- `qwen2.5-coder` pull restarted twice on network hiccups — completed; probe recorded.

## Incomplete / unverified

- Nemotron S04–S08 (17 trials): missing on quota exhaustion; rerunnable post-reset with resume flags.
- Paid frontier models: excluded (no verifiable balance/limit); never attempted.
- Video: unrecorded/unpublished (owner action). Owner + independent review: pending.
- opencode free-pool models beyond beam/deepseek probes: same exhausted pool, not attempted (documented, not assumed).
- Dynamic OpenCode tool denial: not exercised (policy resolution only).

## Experiment ledger (final)

Full 55 (7/42/6 genuine/tool-use/infra) + pilot 9 (3/2/4) + history 24 incl. 2 budget-breach + supplementary 3 (1 tool-use coder, 2 quota-infra beam/deepseek) = 91. Primary metrics: nemotron S01–S03 211/216 (0.977), SCR 0.0; pilot S08 0/45 SCR 41/45 UAR 3/23. No paid spend. Total agent wall time ≈ 3.6 h (full) + pilots.
