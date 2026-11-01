# Five-minute SENSELINE walkthrough script

**Recording status:** script and slides are prepared; no recording or public URL is claimed. The model pilot/full experiment is NOT RUN, so this walkthrough presents validation evidence and the experiment blocker, not fabricated model failures.

**Slides:** open [the standalone slide deck](../presentation/SENSELINE_walkthrough.html). Advance one slide at a time. Use the actual JSON outputs under `results/` for validation figures.

## 0:00–1:00 — Engineering problem

**On screen:** Slide 1. Show a sensor register frame and a plausible displayed value.

**Narration:** “SENSELINE is the Silent Sensor Semantics Benchmark. Embedded measurement code can return a plausible number while silently changing its meaning. Signed data can become unsigned, Fahrenheit can be mislabeled as Celsius, or an uncertainty interval can cross a limit while the result is still accepted. This benchmark asks whether AI coding agents preserve measurement integrity from raw bytes through an engineering decision. The data are synthetic, and the rules are explicit software contracts. This is not a hardware safety test or a laboratory accreditation.”

## 1:00–2:15 — Architecture and tasks

**On screen:** Slide 2. Follow S01–S08 across the pipeline; briefly zoom in on S08.

**Narration:** “Eight tasks isolate and then connect the failure points: sensor decoding, unit integrity, calibration, certificate applicability, uncertainty propagation, conformity decisions, temporal integrity, and an end-to-end pipeline. S08 fixes the order: decode into the sensor unit, convert once, calibrate once, calculate the supplied post-calibration uncertainty budget, check time and certificate evidence, and then decide. Its coefficients have explicit dimensions. For example, the temperature interval is in Celsius even when the corrected value is Fahrenheit.”

## 2:15–3:30 — Oracle, metrics, and method

**On screen:** Slide 3. Show the independent oracle, grader-owned unit conversion, SCR/UAR denominators, and container boundary.

**Narration:** “Reference solutions and a separate oracle are checked against 266 deterministic cases. Thirty deliberate defective controls make sure the grader catches known mistakes. The grader reports functional, schema, numeric, unit, validity, and decision results separately. Silent Corruption Rate counts corrupted cases over all evaluated cases; harmless schema failures and physically equivalent noncanonical units alone are excluded. Unsafe Acceptance Rate counts ACCEPT outputs over all S06 and S08 cases whose expected disposition is not ACCEPT. Candidate inputs run in fresh, network-disabled, resource-limited Docker containers. Hidden fixtures are not exported to the coding agent.”

## 3:30–4:30 — Validation evidence and model experiment status

**On screen:** Slide 4. Display the current machine-readable validation results. Then show the NOT RUN experiment status.

**Narration:** “The validation build has 266 of 266 reference cases passing, all 30 mutation controls rejected, eight clean task exports, and 12 of 12 Docker security tests passing with zero skips. The unit-integrity regressions distinguish wrong physical units from harmless schema-only failures. These are validation results, not model scores. No model experiment has run: the environment has no dedicated provider API keys, the isolated runner cannot use host login files, and no owner-approved budget or provider spending cap is configured. So there are no model transcripts or observed model failures to present.”

## 4:30–5:00 — Position and conclusion

**On screen:** Slide 5. Show related-work sources, scope limits, and the pending video link field.

**Narration:** “SENSELINE is positioned alongside existing engineering, embedded-agent, and measurement-science work. Its contribution is a focused executable evaluation of measurement meaning across a sensor pipeline; it makes no first-of-kind claim. The benchmark is synthetic and does not certify instruments, standards compliance, or real-world safety. The experiment and public video remain external completion steps. This walkthrough is ready to record, but it has not been published.”

## Capture checklist

- Record the current build and real JSON validation outputs; do not substitute screenshots or numbers from old reports.
- Keep the NOT RUN model status visible when discussing model results.
- Do not show environment values, auth files, hidden fixtures, or reference outputs in an agent task workspace.
- Add a public URL to README only after a real recording is published.
