# OWNER REVIEW REQUIRED — decision packet (status: PENDING)

No owner approval is claimed anywhere in this submission. Operator (MuseSpark) review is
recorded; owner review is explicitly pending. Do not treat operator review as owner sign-off.

## 1. The two over-budget trial records

| Run | Tokens / budget | Score | Status |
|---|---|---|---|
| pilot-history attempt4 S08 (`20261105T204856`), nemotron | 82740 / 60000 | graded snapshot 32/45, UAR 2/23 | BUDGET_BREACH |
| pilot-history truncated S01 (`20261106T010759`), nemotron | 64271 / 60000 | graded snapshot 31/32 | BUDGET_BREACH (already excluded) |

Both ran under a 60k per-trial token budget that was an editing error (the other two
configurations already carried 120k); the uniform budget is now 120k. The enforcer killed
both agents (exit 1) before completion. Raw transcripts, snapshots, and grading outputs are
preserved (`results/pilot-history/`).

## 2. Why they are excluded from primary metrics

The registered execution budget (120000 tokens/trial, 900 s wall time) is part of the
experiment protocol (`configs/experiment_matrix.json`). A trial terminated by the budget
enforcer did not execute under its registered budget, so it is INCOMPLETE by protocol —
functionally a `BUDGET_BREACH` subclass. Including cut-off snapshots in primary metrics
would reward or punish partial work as if it were a completed attempt. They are reported
as budget findings (`reports/FINAL_EXPERIMENT_ANALYSIS.md`, "Budget-breach findings").

## 3. Original experiment protocol

9-trial pilot (S01/S05/S08 × 3 configs × 1 trial) → operator review + recorded approval →
72-trial full run (8 tasks × 3 configs × 3 trials), identical task specs, budgets, and
grading; fresh workspace per trial; Docker-isolated grading; fail-closed on sandbox loss.
Spend: strict $0 (local + documented $0 models; paid paths require hard limits + credentials).

## 4. Approval-state discrepancy

`results/pilot/pilot_approval.json` records `approved: true` with
`reviewer: "release operator …"` and `owner_review: "PENDING"`. The full run launched on
operator approval only — a documented gate deviation (see `reports/FINAL_RELEASE_AUDIT.md` §3).
Nothing in the repository represents this as owner approval.

## 5. Full-run protocol deviation

One nemotron supplementary trial ran under the erroneous 60k budget before the error was
found (the 64271-token record above). The matrix was corrected to uniform 120k, the
truncated trial was excluded, and the 7-trial nemotron full set is uniformly budgeted.
No task, grader, tolerance, or fixture was changed for any model at any time.

## 6. Cost uncertainty

Estimated cost $0 for all trials (zero-cost tier). Confirmed billing: unverified — no
paid call was made and no billing dashboard was pulled. Residual uncertainty the owner could close: the OpenRouter account shows
usage +$0.0016 total (4.9868 → 4.9876 → 4.9884, two +$0.0008 steps) across free-tier probing against $5 prepaid credits (usage now ~$5.02); the
project cannot confirm from inside whether micro-increments reflect billable events —
only the account holder's billing record can, and the counter must not be equated with billing. Provider hard-spend-limit evidence was not
obtainable for paid paths, so paid models were excluded rather than attempted.

## 7. Corrections made to the research analysis

- GENUINE/TOOL_USE/INFRA/BUDGET_BREACH classification generated from raw records
  (`scripts/analyze_results.py`), replacing pooled aggregates; phase counts verified
  (full 7/42/6/0, pilot 3/2/4/0, history 4/13/5/2, supplementary 0/1/2/0; total 14/58/17/2 of 91).
- UAR 2/23 vs 3/23 resolved per-run and never pooled (32/45 exploratory budget-breach run SCR 7/45 UAR 2/23 vs 0/45 genuine run SCR 41/45 UAR 3/23).
- 32/45 run traced to its canonical record (`results/pilot-history/pilot-attempt4-9trials-budgetbreach/.../20261105T204856...`).
- Stale "17/16 GENUINE" corrected to 14 (7 full + 3 pilot + 4 history; 2 budget-breach trials excluded).
- `aggregate.json` labeled as raw harness record (55 full trials pooled regardless of eligibility); canonical metrics are eligibility-aware (`experiment_analysis.json`).
- pass@3/pass^3 fixed to key trials by run_id (overall genuine now 1/11, full nemotron 1/2); groups with <3 genuine trials contribute null.

## Decision statement for the owner

1. Approve or reject the BUDGET_BREACH exclusion rule (§2).
2. Approve or reject operator-reviewed pilot/full evidence as the submission basis.
3. Authorize (or decline) a post-reset nemotron S04–S08 rerun and any paid-model evaluation
   with an explicit cap and provider hard limit.
4. Record and publish the five-minute walkthrough; replace the README PENDING marker with
   the public URL.
5. Confirm independent technical review requirements, if any.

Until (1)–(2) are signed, the submission remains READY_WITH_DISCLOSED_LIMITATIONS, not READY.
