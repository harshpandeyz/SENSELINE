# SENSELINE Final Release Audit

Audit date: 2026-11-06 UTC. Auditor: release operator (MuseSpark build). Owner review: pending.
Canonical evidence: `results/experiment_analysis.json` (91 trials: 14 GENUINE, 58 TOOL_USE, 17 INFRA, 2 BUDGET_BREACH; generated from raw records by `scripts/analyze_results.py`, verified by recomputation). Raw records: `results/runs/`,
`results/pilot/`, `results/pilot-history/`, `results/supplementary/`, `results/transcripts/`.
Release artifact: `dist/SENSELINE_SUBMISSION_CANDIDATE.zip` + sidecar `.sha256` (artifact identity per the sidecar checksum; verified by the independent fresh-extraction gate with TECHNICAL_PASS + PENDING_VIDEO — see `results/archive_validation.json` in the source tree and the packaging log). Final uploadable `dist/SENSELINE_FINAL_SUBMISSION.zip` is built only by `scripts/finalize_submission.py` after the owner supplies the real public URL. Earlier releases preserved in `dist-archive/`.
Git: branch `main` pushed to `https://github.com/harshpandeyz/SENSELINE` (no force-push).
Content commit `e950815`; remote sync merged the owner's deletion of stale
`FINAL_AUDIT_REPORT.md`. Release-time tip `406622c` (audit-reference commits only).

## 1. Project state

Eight tasks S01–S08 with frozen specs, schemas, public examples, and starters; independent oracle
(`oracle/compute.py`, imports no reference code); reference implementations (`reference/`);
grader (`graders/grade.py`) with unit-aware SCR/UAR; Docker-isolated candidate runtime
(`harness/secure_execution.py`, pinned image `python:3.11.18-slim-bookworm@sha256:ef521de1…`);
three-profile harness (`configs/opencode.json` v2.2.5 CLI). Prior narrative audit reports were absent
from the checkout; all retained JSON artifacts were re-verified by re-execution, not trusted.

Complete: benchmark code, grader validation, security validation, 55/72-trial full experiment +
9-trial pilot with transcript-backed failure analysis, reproducible packaging.
Incomplete: nemotron S04–S08 block (17 trials, quota-exhausted), public video URL, owner review.
Inconsistent (all resolved): pilot 60k/120k budget split (fixed; truncated trial preserved as evidence
and excluded), validator placeholder rule (fixed to accept real URL / explicit PENDING), stale
"NOT RUN" documentation (rewritten to evidence).

## 2. Required audit table

| Item | Evidence / result |
|---|---|
| Benchmark tests | `pytest`: **134 passed, 0 skipped** (104 benchmark + 30 finalizer) (2026-11-06; one run showed 11 docker-integration skips while the Docker daemon was down — daemon restarted, image verified, suite re-run green) |
| Oracle | 266/266 hidden fixtures: reference and independent oracle agree exactly |
| Mutation suite | **30/30 rejected** for an intended failure dimension |
| Docker security | **12/12 PASS, 0 skipped**; Codex CLI 0.164.0-alpha.11.1 sandbox checks PASS; OpenCode 2.2.5 policy resolves (dynamic tool denial not exercised — disclosed) |
| Python environment | 3.11.16 venv, pinned `requirements.txt`; clean-install verified from extracted archive (see validation report) |
| Model experiments | Full 55 (GENUINE 7, TOOL_USE 42, INFRA 6) + pilot 9 (3/2/4) + history 24 (4/13/5/2 incl. 2 BUDGET_BREACH) + supplementary 3 (0/1/2/0). Total 91 (14/58/17/2). BUDGET_BREACH trials (S08 82740 tokens, S01 64271 tokens) preserved as evidence and excluded from primary metrics |
| Coverage (genuine) | Nemotron full: S01×3, S02×3, S03×1; pilot S01/S05/S08 × 1; history S01×1 + S05×1 + 2 BUDGET_BREACH. S04/S06/S07: no genuine coverage anywhere. S05/S08 genuine: pilot only. Missing 17 full-run slots (S03×2, S04×3, S05×3, S06×3, S07×3, S08×3) absent, not zero |
| SCR (genuine) | Nemotron full S01–S03: **0/216 = 0.0**; genuine pilot S08: **41/45 = 0.911** (run B 0/45). Exploratory budget-breach S08 snapshot (run A 32/45): SCR **7/45**, kept separate and excluded. Local models: no genuine code, SCR not applicable (0 valid claims) |
| UAR (genuine) | Genuine pilot S08: **3/23** (run B). Exploratory budget-breach S08: **2/23** (run A), kept separate and excluded. Never pooled (no 5/46). Full: null denominator (no S06/S08 genuine cases) |
| Accuracy (genuine) | Nemotron full: **211/216 = 0.977** (S01 91/96, S02 90/90, S03 30/30); macro task avg 0.983; pass@3 = pass^3 = **1/2** full (S02 perfect; strict perfect-trial definition) and **1/11** overall genuine pooled (run_id-keyed; S01 n=5 + S02 n=3). Groups with <3 genuine trials contribute null |
| Cost | Configured cap **$0** (enforced: paid paths require hard limits + credentials; none present). Estimated $0 all trials. Confirmed billing: unverified (no billing dashboard pulled; counter ≠ billing). Provider counter +$0.0016 total (4.9868 → 4.9876 → 4.9884, two +$0.0008 steps) across free-tier probing (disclosed) |
| Packaging | `dist/SENSELINE_SUBMISSION_CANDIDATE.zip` (technical candidate, README with `VIDEO_URL_PENDING_OWNER_UPLOAD` at root, < 50 MB, SHA-256 sidecar) + `scripts/finalize_submission.py` to rebuild `dist/SENSELINE_FINAL_SUBMISSION.zip` once the owner supplies the real public URL. Both use the official inclusion/exclusion rules; candidate validation reports TECHNICAL_PASS + PENDING_VIDEO |
| Reproducibility | Fresh-directory extraction + dependency install + tests + validation + security: see `reports/FINAL_VALIDATION_REPORT.md` and `results/archive_validation.json` (candidate mode) |
| Security | No candidate code on host (DockerCandidate only); non-root, no-network, read-only, capped containers; hidden fixtures never exported (visible in repo/ZIP for judge reproducibility — agent-confidential, not repo-confidential); secret scan clean; transcripts redacted, contain operator-local paths (no credentials) |
| Video | **PENDING** — no URL invented; README carries `VIDEO_URL_PENDING_OWNER_UPLOAD`; candidate validator allows it (PENDING_VIDEO), final validator rejects it; owner action required (`python scripts/finalize_submission.py --video-url "REAL_PUBLIC_VIDEO_FILE_URL"`) |
| Human review | Operator (transcript-level, all phases); **owner review pending** — `results/pilot/pilot_approval.json` records `approved:true` by operator criteria with `owner_review: PENDING`. Full run proceeded on operator review; chronology and gate deviation documented below |
| GitHub | Branch `main`; final commit + push status recorded at release time (see §7) |

## 3. Experiment chronology and protocol deviations

1. Matrix configured zero-cost ($0 caps, 60k tokens) → pilot attempts 1–3 exposed a harness
   setup-block defect (fixed), transient Ollama no-route flakes (bounded retry + continue rule added),
   and a 60k token breach on nemotron S08 (budget raised to 120k for all configs).
2. Pilot attempt 5: 9/9 PILOT_COMPLETE. Operator reviewed all transcripts; approval file written
   with reviewer honestly marked operator and `owner_review: PENDING`.
3. Full run launched on operator approval (gate deviation: owner review still pending — disclosed,
   not fabricated). Ran 48 local trials + 1 nemotron trial, then halted by design on a second
   60k breach (editing error: nemotron config kept 60k while the other two were raised to 120k).
4. Truncated trial preserved as evidence and excluded; nemotron budget corrected to uniform 120k;
   resume flags (`--only-config`, `--skip-completed`) added; supplementary nemotron block ran 6
   more trials, then halted by design with QUOTA_EXHAUSTED (50/day free quota at ~8–11
   requests/agentic trial). Final: 55/72.
5. No task, grader, tolerance, or fixture was changed to suit any model at any point.

## 4. Discrepancies investigated (previous audit)

- Stale "17/16 GENUINE", "90 trials", "INFRA 15/16", "supplementary 1/2", "89-trial", "1/5 pass", "pooled 5/46 / 41/107", and "+$0.0008" phrasing: all reconciled to verified 91 trials (14 GENUINE = 7 full + 3 pilot + 4 history; 58 TOOL_USE; 17 INFRA = 6+4+5+2; 2 BUDGET_BREACH in history; supplementary 3 = 1 TOOL_USE + 2 INFRA). Fixed in all documents; overall genuine pass@3/pass^3 corrected from 1/5 (trial-number collision across phases) to run_id-keyed 1/11.
- "UAR 2/23 vs 3/23": both correct, different runs and never pooled — 2/23 = attempt-4 budget-breach S08 32/45 snapshot (SCR 7/45, excluded); 3/23 = genuine pilot S08 0/45 run (SCR 41/45, canonical). Now reported per-run with IDs.
- "Untraceable 32/45": traced to `results/pilot-history/.../20261105T204856...` (imported from
  preserved evidence dir into the repo). Resolved.
- `aggregate.json` vs classification-aware analysis: aggregate pools all Docker-graded trials
  (raw harness record); canonical metrics come from `experiment_analysis.json` (GENUINE only).
  Both ship; docs state the distinction. Statuses reading COMPLETE in
  `experiment_status.json` mean "3 trials present per task", not "3 genuine" — documented.
- `pilot_approval.json`: `approved:true` reflects operator review only; `owner_review: PENDING`
  preserved; full run on operator approval documented as a gate deviation above.

## 5. What was not done (honest limitations)

- Nemotron S04–S08 (17 trials): missing on free-quota exhaustion. Rerun path: after 00:00 UTC
  reset with the same matrix (`--only-config openrouter-nemotron-vl-free --skip-completed`).
- Paid frontier models (GPT/Claude/NVIDIA-direct/Meta): untestable under $0 — credits exhausted,
  wrong-slot key, no verifiable limits. Documented, not attempted.
- Video: unrecorded/unpublished. Owner action.
- Owner review + independent metrology review: pending. Not claimed.

## 6. Release decision

**TECHNICALLY COMPLETE — AWAITING VIDEO** (equivalent to READY_WITH_DISCLOSED_LIMITATIONS for the
technical package). The candidate ZIP passes all technical gates (tests, reference/mutation,
Docker security, packaging, fresh-extraction) with VIDEO_URL PENDING and SUBMISSION_READINESS
PENDING_VIDEO. Pending external items the operator cannot fabricate: public video URL +
final rebuild via `finalize_submission.py`, owner review, quota-gated S04–S08 rerun, and
independent metrology review. See `reports/FINAL_VALIDATION_REPORT.md` for the extraction check.
Never claim READY TO SUBMIT while the video URL remains pending.
