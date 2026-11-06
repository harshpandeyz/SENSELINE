# Five-minute SENSELINE walkthrough script

**Recording status:** script and slides are updated to the 2026-11-06 evidence (55 full-run + 9 pilot trials, 16 genuine). No recording or public URL exists. The README carries an explicit PENDING marker; never invent a URL.

**Slides:** open [the standalone slide deck](../presentation/SENSELINE_walkthrough.html). Advance one slide at a time. Use the actual JSON outputs under `results/` (not old reports): `results/experiment_analysis.json` for model metrics, `results/reference_validation.json` for controls.

## 0:00–1:00 — Engineering problem

**On screen:** Slide 1. Show a sensor register frame and a plausible displayed value.

**Narration:** “SENSELINE is the Silent Sensor Semantics Benchmark. Embedded measurement code can return a plausible number while silently changing its meaning. Signed data can become unsigned, Fahrenheit can be mislabeled as Celsius, or an uncertainty interval can cross a limit while the result is still accepted. This benchmark asks whether AI coding agents preserve measurement integrity from raw bytes through an engineering decision. The data are synthetic, and the rules are explicit software contracts. This is not a hardware safety test or a laboratory accreditation.”

## 1:00–2:15 — Architecture and tasks

**On screen:** Slide 2. Follow S01–S08 across the pipeline; briefly zoom in on S08.

**Narration:** “Eight tasks isolate and then connect the failure points: sensor decoding, unit integrity, calibration, certificate applicability, uncertainty propagation, conformity decisions, temporal integrity, and an end-to-end pipeline. S08 fixes the order: decode into the sensor unit, convert once, calibrate once, calculate the supplied post-calibration uncertainty budget, check time and certificate evidence, and then decide. Gain is dimensionless, offset is in the final unit, and the temperature interval is Celsius even when the corrected value is Fahrenheit.”

## 2:15–3:30 — Oracle, metrics, and method

**On screen:** Slide 3. Show the independent oracle, grader-owned unit conversion, SCR/UAR denominators, container boundary.

**Narration:** “Reference solutions and a separate oracle are checked against 266 deterministic cases. Thirty deliberate defective controls make sure the grader catches known mistakes. Every trial is classified genuine, tool-use failure, or infrastructure failure — only genuine trials enter model metrics. Silent Corruption Rate counts corrupted cases over evaluated genuine cases; harmless schema failures alone are excluded. Unsafe Acceptance Rate counts ACCEPT outputs over S06/S08 cases whose expected disposition is not ACCEPT. Candidate inputs run in fresh, network-disabled, resource-limited Docker containers. Hidden fixtures are not exported to the coding agent. All 72 planned trials run under a zero-dollar API cap.”

## 3:30–4:30 — Experiment results (actual)

**On screen:** Slide 4. Display `results/experiment_analysis.json` figures: 55/72 full trials plus 9 pilot; 16 genuine; per-model table.

**Narration:** “Fifty-five of seventy-two planned trials executed before the free-tier quota halted the run by design; nine pilot trials completed separately. Of eighty-nine preserved trials, sixteen are genuine. The strong configuration, Nemotron Super-VL, scores two-eleven of two-sixteen on sensor decoding, units, and calibration with zero silent corruption — its only misses are reason-string vocabulary on correctly rejected inputs. But pilot end-to-end runs show the core failure: correct arithmetic with dropped certificate evidence and malformed frames accepted anyway — five unsafe acceptances in forty-six non-acceptable cases. The two small local models never engaged the file tools: fifty-eight tool-use trials with zero implementations, a reproducible agent-capability boundary, not a reasoning score. Ten infrastructure trials are excluded from every metric. Nemotron tasks S04 through S08 are missing on quota — absent, not zero — and paid frontier models were unavailable under the zero-dollar cap.”

## 4:30–5:00 — Position and conclusion

**On screen:** Slide 5. Show related-work sources, scope limits, and the pending video link field.

**Narration:** “SENSELINE is positioned alongside existing engineering, embedded-agent, and measurement-science work. Its contribution is a focused executable evaluation of measurement meaning across a sensor pipeline; it makes no first-of-kind claim. The benchmark is synthetic and does not certify instruments, standards compliance, or real-world safety. The remaining work is external: rerunning the missing end-to-end block after the quota reset, publishing this walkthrough, and completing owner review. This script is ready to record.”

## Capture checklist

- Record the current build and real JSON validation outputs; do not substitute screenshots or numbers from old reports.
- Show the GENUINE/TOOL_USE/INFRA split whenever model results appear.
- Do not show environment values, auth files, hidden fixtures, or reference outputs in an agent task workspace.
- Add a public URL to README only after a real recording is published.
