# Failure analysis

## Observed model results

**Model experiment status: NOT RUN.** As of 2026-11-02, there are no SENSELINE model trials, candidate outputs, model transcripts, model scores, measured model runtimes, or API costs. Therefore, there are no observed model failures to classify or reproduce. Do not interpret the mutation controls or reference validation as model behavior.

The OpenCode v2.2.5 catalog and provider-profile list were inspected; the local OpenCode auth list showed OpenAI, OpenRouter, NVIDIA, and Meta profiles, while no Anthropic profile was present. The process environment had no dedicated provider API-key variables. Codex CLI 0.164.0-alpha.11.1 reported a ChatGPT login, but the harness deliberately creates a fresh CODEX_HOME and will not copy host login files. One local model, ollama/qwen3:8b, is installed; this is one local configuration, not the required three-model design. No owner-approved spend cap or provider hard-spend-limit evidence exists. No inference request was started.

| Required failure evidence | Current state |
| --- | --- |
| Task ID and exact model/agent version | No trial records |
| Actual candidate output and expected outcome | No candidate outputs |
| Failed invariant and engineering explanation | Not classifiable without a genuine failure |
| Reproducibility across attempts | Not measured |
| Grader defect versus incomplete implementation versus runtime failure | Not classifiable without a trial |

## Failure families the benchmark can detect

The following are test categories and mutation-control targets, not observed model failures:

1. **Signedness, endianness, and fixed point (S01):** wrong two's-complement decoding, byte order, width, scale, sentinels, or malformed-frame rejection.
2. **Unit conversion (S02, S08):** affine-conversion mistakes, incompatible dimensions, an incorrect label, a missing required unit, or a physically non-equivalent value/unit pair.
3. **Calibration (S03, S08):** gain/offset order, omitted temperature compensation, double correction, or coefficient-unit mistakes.
4. **Certificate validity (S04, S08):** instrument/measurand mismatch, status/date/range errors, uncertainty validity, unit mismatch, and missing traceability evidence.
5. **Uncertainty and covariance (S05, S08):** Type A/Type B errors, ignored sensitivity or contributors, dropped covariance, invalid correlation matrices, or incorrect expanded uncertainty.
6. **Conformity (S06, S08):** point-only decisions, wrong inclusive boundaries, malformed limits, unsafe acceptance, and false rejection.
7. **Temporal validity (S07, S08):** stale/future readings, clock skew, duplicate/order errors, and uint32 rollover/half-range errors.
8. **Cross-layer S08 interactions:** a stage failure not retained, uncertainty rescaled despite being post-calibration, or a final disposition emitted despite invalid evidence/time/data.

The most recent validation artifacts are [results/reference_validation.json](../results/reference_validation.json), [results/unit_integrity_validation.json](../results/unit_integrity_validation.json), and [results/docker_security_validation.json](../results/docker_security_validation.json). Their results describe trusted references, deliberate controls, and sandbox attacks only. Replace this section's NOT RUN status with a transcript-backed analysis only after an authorized pilot and full experiment complete.
