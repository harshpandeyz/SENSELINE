# SENSELINE methodology and scoring

Protocol version: 0.3.1. The frozen hidden fixture suite contains 266 cases across eight tasks. Each task has an explicit input/output schema, public examples, deterministic hidden fixtures, a reference solution, and an independently implemented oracle. The oracle imports no reference code; the grader owns a third set of unit transformations. Executed 2026-11-05/06 UTC: 91 classified trials (14 GENUINE, 58 TOOL_USE, 17 INFRA, 2 BUDGET_BREACH) under a strict $0 cap; canonical eligibility-aware analysis is `results/experiment_analysis.json` generated from raw records by `scripts/analyze_results.py`.

## Construct and scope

The benchmark measures whether generated code preserves the represented physical quantity and its validity from register decoding through unit conversion, calibration, uncertainty, calibration evidence, temporal checks, and conformity decisions. Inputs are synthetic. The task rules are bounded executable contracts, not instrument validation, a general implementation of the GUM, standards compliance, accreditation, or safety certification.

## Metrics and denominators

Metrics are computed once per evaluated hidden case. For a set of task reports, denominators are pooled case counts; task rates are also reported individually. A trial with all tasks is not averaged equally by task for SCR or UAR. Each case contributes at most once to a numerator.

### Silent Corruption Rate (SCR)

    SCR = N_corrupt / N_evaluated

`N_evaluated` includes every scheduled hidden case, including malformed outputs, runtime errors, timeouts, and container failures. `N_corrupt` counts a case if any of these holds:

1. A candidate claims `valid=true` or decision `ACCEPT`, and one or more expected numeric physical outputs are missing, unparseable, or outside the declared tolerance after applicable unit-pair conversion; or a supplied unit is dimensionally incompatible or not physically equivalent to its value.
2. A ground-truth false validity field is promoted to true. This includes the top-level validity field and, in S08, temporal and calibration validity.
3. The expected S06/S08 disposition is not `ACCEPT`, but the candidate returns `ACCEPT`.

The corruption numerator is a count of cases, not reasons. Multiple corruption reasons in one case still add one. A harmless extra field, a numeric JSON-type/format violation with the same parseable physical value, or an equivalent noncanonical unit pair alone is a contract/schema failure and is excluded from SCR. A wrong supplied unit label that changes the represented physical quantity or an incompatible dimension is SCR when claimed valid. A missing required unit on an otherwise numerically correct valid result is a semantic integrity failure and strict-contract failure, but is excluded from SCR because the grader cannot infer a physical unit from the omitted label. If the numeric result is also wrong or unparseable, it counts toward SCR. A unit pair that is equivalent but violates the task's required canonical representation is not physical corruption under this definition.

### Unsafe Acceptance Rate (UAR)

    UAR = N_unsafe_accept / N_nonacceptable

`N_nonacceptable` is the number of S06 and S08 cases whose oracle disposition is not `ACCEPT`. This includes invalid S06 inputs with no disposition. `N_unsafe_accept` counts those cases where the candidate disposition is `ACCEPT`. Malformed/non-object output and execution failures remain in the denominator but cannot enter the numerator without an `ACCEPT` disposition. A schema-invalid object with a parseable `ACCEPT` still counts. The global UAR pools S06 and S08 case counts; per-task UAR is reported separately. A zero denominator is reported as null.

### Other registered metrics

Functional correctness requires both schema validity and exact semantic agreement within declared numeric tolerances. Schema compliance, numeric correctness, unit-label correctness, physical equivalence, semantic integrity failures from missing required units, validity-state correctness, engineering-decision correctness, execution failures, malformed-response rate, false-rejection rate, and end-to-end S08 correctness have separate metrics. Numeric accuracy uses converted values when a supported unit is supplied; if the unit is missing or unsupported, the scalar is checked independently and the unit metrics carry the interpretation failure. Numeric errors are grouped by task, field, and unit; errors in different dimensions are never pooled. Zero-denominator rates are null.

## Unit-aware grading

S02 compares the returned value/unit pair with the requested `to_unit`; S08 separately grades decoded input (`from_unit`), converted physical quantity (`to_unit`), and corrected measurement (`to_unit`). The grader's affine conversion table is independent from both reference and oracle implementations. Strict schema and canonical-unit compliance remain separate from physical equivalence. A Celsius value returned as an equivalent Fahrenheit value is physically equivalent but contract-invalid; a numerically plausible value paired with a unit that represents a different quantity is physical corruption when claimed valid.

## S08 dimensional and numerical contract

The order is fixed:

1. Decode and scale register data into `units.from_unit`; apply the S01 sensor rounding once.
2. Convert once from `from_unit` to `to_unit` using the S02 affine rules; do not round again at this stage.
3. Apply calibration once: `corrected = gain × physical_value + offset + temperature_coefficient × (ambient_C − reference_C)`. Gain is dimensionless, offset is in `to_unit`, the coefficient is `to_unit/°C`, and the temperature difference is a Celsius interval even when output is Fahrenheit or Kelvin. Apply only the specified calibration rounding.
4. Evaluate the supplied S05 uncertainty budget after calibration. Type A observations and Type B half-widths are already in `to_unit`; do not multiply them by gain or convert them again. Sensitivity coefficients are dimensionless under this task contract. Each standard uncertainty and combined/expanded uncertainty is in `to_unit`; covariance `rho_ij u_i u_j` is in `to_unit²`.
5. Check calibration evidence against the corrected value, output unit, instrument, measurand, and date.
6. Apply the S06 interval decision to corrected value, expanded uncertainty, and limits, all in `to_unit`.

Certificate uncertainty is checked for validity but is not combined with the supplied budget because its distribution, coverage factor, and correlation are unspecified. Any invalid stage blocks a valid final disposition; independent temporal, uncertainty, and certificate failures are retained in specified order.

The S08 suite includes Fahrenheit-to-Celsius conversion with calibration, Celsius-to-Fahrenheit output with a Celsius temperature interval, signed decoding plus environmental compensation, correlated rectangular contributors, Type A and post-calibration uncertainty, conformity and calibration-range boundaries, stale measurements with valid certificates, simultaneous defects, and valid complete pipelines. Golden values are checked against hand calculations and frozen outputs without changing expected results to fit implementations.

## Experiment design and status

The pilot is 3 tasks (S01, S05, S08) × 3 model configurations × 1 trial = 9 trials. Only after pilot transcript review and recorded approval may the full design run: 8 tasks × 3 configurations × 3 trials = 72 trials. The same task export, agent profile/permissions, budgets, trial initialization, sandbox, and grader apply across configurations. Report model and agent versions separately.

Executed 2026-11-05/06 UTC under a strict $0 API cap with three zero-cost configurations (opencode v2.2.5 agent for all; `ollama/qwen3:8b` and `ollama/llama3.2:1b` local; `openrouter/nvidia/nemotron-3.5-super-vl:free` documented $0 free-tier; uniform 120000-token and 900 s-agent budgets; exact matrix in `configs/experiment_matrix.json`). Full run: 55 trials before a designed QUOTA_EXHAUSTED halt (OpenRouter 50-request/day free quota consumed at ~8–11 requests per agentic trial); pilot: 9 trials PILOT_COMPLETE; 24 pilot-history and 3 supplementary trials preserved with phases labeled. Every trial is classified GENUINE / TOOL_USE / INFRA / BUDGET_BREACH (`scripts/analyze_results.py`): BUDGET_BREACH trials (budget enforcer cut the agent off mid-work) keep their evidence but are excluded from primary metrics because they did not execute under their registered budget. Model metrics pool GENUINE trials only. Pass@3 (any-of-3 perfect trials) and pass^3 (all-3 perfect) require 3 genuine trials per (model, task). `results/experiment_status.json` is the harness's raw record (trial presence, not eligibility); `results/experiment_analysis.json` is the canonical classification-aware analysis.

## Transcript and reproducibility record

For each future trial, the harness records the exact task instruction/prompt, trial seed, exact model and agent version, profile and settings, candidate snapshot/hash, agent stdout/stderr and actual structured events, candidate outputs, per-case grading reasons, runtime, available usage metadata, and pinned sandbox image digest. Agent-reported cost is an estimate, not confirmed billing. Private model reasoning is not requested or recorded. Each trial starts in a fresh task-only workspace; each candidate input gets a fresh sandbox container.

## Security boundaries

The agent receives a clean task export in a temporary workspace, task-local HOME/config paths, and only explicitly allowlisted provider credential variables. The candidate never inherits agent credentials and runs in a network-disabled, non-root Docker container with read-only mounts, dropped capabilities, no-new-privileges, and resource/wall-time limits. Hidden fixtures and grader files are included in the repository and submission archive so judges can reproduce grading; they are not exported into agent task workspaces and are never mounted into candidate containers. If Docker/image preflight fails, execution stops before agent launch; no host Python fallback is allowed.
