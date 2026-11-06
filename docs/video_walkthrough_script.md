# Five-minute SENSELINE walkthrough script

**Recording status:** script and slides reflect the 2026-11-06 evidence (91 classified trials:
14 GENUINE, 58 TOOL_USE, 17 INFRA, 2 BUDGET_BREACH). No recording or public URL exists.
The README carries an explicit PENDING marker; never invent a URL.

**Slides:** open [the standalone slide deck](../presentation/SENSELINE_walkthrough.html). Advance one slide at a time. Use the actual JSON outputs under `results/` (not old reports): `results/experiment_analysis.json` for model metrics, `results/reference_validation.json` for controls.

## 0:00–0:40 — The engineering problem

**On screen:** Slide 1. A sensor register frame and a plausible displayed value.

**Narration:** “Embedded measurement code can return a plausible number while silently changing what it means. Signed data becomes unsigned. Fahrenheit is mislabeled as Celsius. An uncertainty interval crosses a specification limit — and the result is still accepted. SENSELINE, the Silent Sensor Semantics Benchmark, asks whether AI coding agents preserve measurement integrity from raw register bytes through the engineering decision. Synthetic data, explicit software contracts. Not a hardware safety test, not a laboratory accreditation.”

## 0:40–1:30 — SENSELINE's central hypothesis

**On screen:** Slide 1 (cont.). Corruption vs contract-failure vs rejection diagram.

**Narration:** “The hypothesis: models fail not where arithmetic is hard, but where meaning must be preserved across layers — decoding into units, converting once, calibrating once, checking certificate evidence, propagating uncertainty, then deciding. A wrong number with the right label is ordinary error. A wrong number claimed valid, or an ACCEPT on evidence that forbids it, is silent corruption — the failure this benchmark is built to catch. Harmless schema quirks and equivalent units in non-canonical form are deliberately excluded from that charge.”

## 1:30–2:30 — Eight tasks and evaluation design

**On screen:** Slide 2. S01–S08 pipeline; zoom into S08.

**Narration:** “Eight tasks isolate the failure points, then S08 connects them end to end: decode, convert once, calibrate once with dimensionless gain and final-unit offset, evaluate a supplied post-calibration uncertainty budget, check time and certificate evidence, then apply the inclusive-interval conformity rule. References and an independent oracle agree on 266 hidden cases; thirty deliberate defective controls verify the grader catches known mistakes. Every trial is classified genuine, tool-use failure, infrastructure failure, or budget breach — only genuine trials enter model metrics. Candidates run in fresh, network-disabled, resource-limited Docker containers; hidden fixtures are never exported. All seventy-two planned trials run under a zero-dollar API cap.”

## 2:30–3:30 — Live demonstration of one physical-corruption failure

**On screen:** Terminal + transcript excerpt (redacted). Run the stored candidate from pilot S08 run B against one case, e.g. `S08-unclear-traceability`.

**Demonstration commands (from a clean checkout):**
1. `make setup && make test` — 134 tests green (104 benchmark + 30 finalizer).
2. `.venv/bin/python -m harness.aggregate --results results` — raw trial record.
3. `.venv/bin/python scripts/analyze_results.py --results results --out /tmp/demo.json` — eligibility classification.
4. Show the graded case: expected `calibration_validity.valid=false`, `disposition INDETERMINATE` (traceability not documented); model output `valid=true`, `ACCEPT`. Point at the two diverging fields.

**Narration:** “Here is one real failure. The certificate has no documented traceability, so the expected verdict is indeterminate with invalid calibration evidence. The model computed the numbers correctly — twenty-five degrees — ignored the evidence rule, declared everything valid, and accepted. That is silent corruption plus an unsafe acceptance, from a model that scores ninety-eight percent on decoding, units, and calibration. The same pattern appears with serial mismatches, invalid coverage factors, and even an invented measurement from a truncated frame.”

## 3:30–4:30 — Experimental findings and model comparison

**On screen:** Slide 4. Per-model table from `results/experiment_analysis.json`.

**Narration:** “Fifty-five of seventy-two planned trials plus nine pilot trials, twenty-four pilot-history trials, and three supplementary probes: ninety-one classified trials, fourteen genuine. Nemotron Super-VL, which holds the substantial genuine full-run coverage, scores two-eleven of two-sixteen on sensor decoding, units, and calibration with zero silent corruption — its only misses are reason-string vocabulary on correctly rejected inputs. But its pilot end-to-end run shows the validity-propagation failure above. The two small local models produced zero genuine full-run implementations — fifty-eight tool-use trials — plus two early genuine qwen pilot-history attempts (combined one of sixty, one passing case): a reproducible agent-capability boundary, not a reasoning score. Seventeen infrastructure trials and two budget-breach snapshots are excluded from every metric. Nemotron tasks S04 through S08 are missing — the free quota ran out — absent, not zero. Paid frontier models were unavailable under the zero-dollar cap, so no frontier claim is made.”

## 4:30–5:00 — Research significance and limitations

**On screen:** Slide 5. Related work, scope limits, pending-items field.

**Narration:** “SENSELINE's contribution is a focused, executable evaluation of measurement meaning across a sensor pipeline, with eligibility-aware scoring that refuses to let tool-use failures or infrastructure noise pose as model quality. It makes no first-of-kind claim. It is synthetic: no accreditation, no safety certification, no independent review yet. Remaining work is external: rerunning the missing end-to-end block after the quota reset, publishing this walkthrough, and completing owner review. This script is ready to record.”

## Capture checklist

- Record the current build and real JSON validation outputs; do not substitute screenshots or numbers from old reports.
- Show the GENUINE/TOOL_USE/INFRA/BUDGET_BREACH split whenever model results appear.
- Demo uses only stored, redacted transcripts — never live credentials, auth files, hidden fixtures, or reference outputs.
- Add a public URL to README only after a real recording is published.
