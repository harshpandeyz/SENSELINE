# SENSELINE

## The Silent Sensor Semantics Benchmark

SENSELINE evaluates whether AI coding agents preserve the physical meaning of sensor data from raw register bytes through calibration, uncertainty, and engineering decisions. It is a deterministic software benchmark built from synthetic measurement data.

Video walkthrough: TO BE ADDED BY PARTICIPANT

## Research question and scope

Can a coding agent implement measurement-processing software without silently changing what a sensor measured or accepting an unsafe result? SENSELINE focuses on unit-aware sensor interpretation and the interactions among decoding, calibration, validity evidence, uncertainty, time, and conformity.

**Domain:** embedded measurement software and applied measurement science. **Technical scope:** sensor decoding, dimensional/unit handling, calibration, uncertainty propagation, evidence validity, temporal integrity, and task-specific conformity decisions. These are the benchmark's evaluation areas, not a claim about a participant's professional credentials.

The benchmark measures executable code against explicit contracts. It does not validate hardware, certify a laboratory, assess compliance with a standard, or establish safety for real measurements. Its uncertainty and conformity rules are deliberately bounded task definitions rather than a general implementation of metrology practice.

## Tasks

| ID | Task | Main risks exercised |
| --- | --- | --- |
| S01 | Raw sensor interpretation | Signedness, byte order, width, scaling, sentinels, malformed frames |
| S02 | Physical-unit integrity | Affine conversion, dimensional compatibility, canonical output units, rounding |
| S03 | Calibration and environmental compensation | Gain and offset order, temperature correction, invalid or repeated correction |
| S04 | Calibration applicability and validity | Instrument and measurand match, status, dates, range, uncertainty, unit, traceability evidence |
| S05 | Measurement uncertainty propagation | Type A and Type B inputs, sensitivities, correlation, positive-semidefinite checks, coverage factor |
| S06 | Conformity decisions | Uncertainty intervals, inclusive limits, malformed limits, unsafe acceptance |
| S07 | Temporal and data integrity | Stale or future data, clock skew, duplicate and reordered samples, uint32 rollover |
| S08 | End-to-end measurement integrity | Decode, time, units, calibration, uncertainty, evidence, and final conformity decision |

Each task package contains its specification, input and output JSON Schemas, public examples, and an unimplemented starter. The hidden fixture set contains 266 cases: S01 32, S02 30, S03 30, S04 37, S05 30, S06 30, S07 32, and S08 45. S08 includes both Fahrenheit/Celsius directions, signed decoding, environmental correction, correlated uncertainty, post-calibration uncertainty, calibration range boundaries, stale data, and simultaneous failures.

## Evaluation architecture and scoring

The reference implementations are in [reference](reference/); the separate numerical oracle is in [oracle/compute.py](oracle/compute.py) and imports no reference code. [graders/grade.py](graders/grade.py) applies independent unit transforms, output schemas, exact semantic checks, and field-specific numeric tolerances. Thirty documented defective controls in [mutations](mutations/) must fail for their intended dimensions. Task export copies only the task statement, schemas, public examples, starter, and a short agent README; it excludes hidden fixtures, expected outputs, grader code, references, and mutations.

Candidates are executed outside the evaluator process. Each hidden case runs in a fresh container on the pinned Python 3.11.18 image with networking disabled, a non-root UID, dropped capabilities, no-new-privileges, read-only filesystems, CPU/memory/process limits, bounded output, and a wall timeout. Missing Docker or the image makes execution fail closed; there is no host-Python fallback. Each model trial receives a new temporary task-only workspace and task-local agent home. OpenCode denies external-directory access, shell execution, subagents, and web tools, and allows edits only to solution.py. Its pinned CLI parsed the policy in a disposable project; no model call was made to exercise a dynamic tool denial. Codex uses a task-local HOME and sandbox profile; the installed CLI check confirmed workspace writes while blocking outside sentinels and local network access. Candidate containers never receive agent credentials.

For each candidate, the Silent Corruption Rate is:

    SCR = corrupted cases / all evaluated hidden cases

A case is corrupted if a candidate claims a result is valid or ACCEPT while returning a wrong or unparseable expected physical value, a supplied dimensionally incompatible or physically non-equivalent unit/value pair; if it promotes a false ground-truth validity state to true; or if it returns ACCEPT when the expected disposition is not ACCEPT. Each case counts once. A missing required unit on a numerically correct result is a semantic integrity and contract failure, but is excluded from SCR because the physical meaning cannot be inferred; if its numeric result is also wrong or unparseable, the case counts in SCR. Harmless schema-only failures and physically equivalent values in a noncanonical unit do not alone count as silent corruption. UAR is false ACCEPTs divided by all non-ACCEPT S06/S08 cases, including invalid S06 cases without a disposition. Both metrics pool cases (not task averages), with per-task rates reported separately. See [docs/METHODOLOGY.md](docs/METHODOLOGY.md) for exact rules and exclusions.

Unsafe Acceptance Rate is:

    UAR = ACCEPT outputs on non-acceptable cases / all non-acceptable S06 and S08 cases

Schema, strict functional correctness, numeric correctness, physical-unit correctness and equivalence, missing-unit semantic integrity, validity-state accuracy, decision accuracy, false rejection, runtime failures, and malformed responses are also reported separately. Numerical errors are grouped by task, field, and unit; incompatible dimensions are never pooled. Metric definitions are implemented in [graders/grade.py](graders/grade.py) and described by the JSON validation outputs in [results](results/).

S08 uses a fixed dimensional contract: decode and scale into the input unit, convert once to the final unit, calibrate once, then evaluate an uncertainty budget already supplied after calibration in the final unit. Gain is dimensionless, offset is in the final unit, and the temperature coefficient is final-unit per °C acting on a Celsius temperature interval. The supplied uncertainty is not rescaled by gain or input-to-output conversion. Certificate uncertainty is checked for validity but is not added because its distribution, coverage factor, and correlation are unspecified.

## Installation and validation

Requires Python 3.11. Docker and the pinned image are required for isolated candidate and security validation. Install the pinned dependencies from a clean checkout with:

    make setup
    make test
    make validate
    make security-test
    make experiment-pilot
    make experiment-full
    make package

The test suite and reference validator need no network after dependencies and the Docker image are installed. OpenCode CLI verification may use npm to obtain the pinned CLI if it is not cached. Experiment targets produce a dry-run plan by default; inference requires an explicitly configured matrix and `EXPERIMENT_EXECUTE=1`, plus all spend controls. Benchmark inference needs outbound access only to an explicitly selected agent provider. Candidate runtime containers have no network.

The sandbox image is not pulled automatically. Prepare it explicitly when Docker is available:

    docker pull python:3.11.18-slim-bookworm@sha256:ef521de1d817dc92a6358c906bbadb9a0b7e38040038642833521b9d582c2233

Export a task into a clean directory for inspection:

    .venv/bin/python -m harness.export_task S01 /tmp/senseline-S01

Run the suite with pytest, the Docker attack suite with [scripts/run_docker_security_tests.py](scripts/run_docker_security_tests.py), agent environment checks with [scripts/verify_agent_security.py](scripts/verify_agent_security.py), and the reference, oracle, mutation, unit-integrity, isolation, and all-eight-task export checks with [scripts/validate_submission.py](scripts/validate_submission.py). The Makefile exposes these as test, security-test, and validate targets. A failed or unavailable Docker check is not counted as a pass.

## Dependencies and environment

Runtime dependencies are Python 3.11 standard library and jsonschema 4.23.0. Pytest 8.3.5 is used for validation. Pinned dependency versions are in [requirements.txt](requirements.txt); package metadata and the Python version constraint are in [pyproject.toml](pyproject.toml). The optional Dockerfile runs only non-Docker integration tests; full isolation checks must run on the host Docker daemon.

Copy [.env.example](.env.example) only as a template. Provider credentials are not committed and are not loaded automatically. Paid model evaluation requires an explicitly selected model, dedicated provider credential, owner-approved experiment cap, and provider-side hard spending limit. The runner blocks execution when these controls are missing. Do not put host login files or general-purpose credentials in an agent workspace.

## Model experiment status and actual results

**Model experiments: NOT RUN (2026-11-02).** No exact model IDs or experiment configurations were selected, and no owner-approved spend cap or provider hard cap was recorded. No inference calls were made; there are no model scores, transcripts, model runtimes, failure rates, or API costs to report. The inspected CLI versions were OpenCode 2.2.5 and Codex CLI 0.164.0-alpha.11.1; those are agent tools, not tested models.

The configured plan starts with a 9-trial pilot (S01, S05, and S08 for three model configurations), then a reviewed and approved 72-trial experiment (eight tasks, three configurations, three trials). Each planned run has a 900-second agent wall limit and a 5-second per-input candidate limit; the pilot uses trial index 0 and the full run uses trials 1–3. Temperature and reasoning-effort settings are unset in the template. Use [configs/experiment_matrix.template.json](configs/experiment_matrix.template.json) to prepare a matrix. Inference requires the explicit `--execute` flag, exact model/agent IDs, dedicated provider credentials, and all spend controls; the full run also requires a completed, reviewed pilot.

No model was tested. The OpenCode CLI inventory exposed candidate IDs including `openai/gpt-5.6`, `openrouter/anthropic/claude-sonnet-4.6`, `nvidia/nvidia/nemotron-3.5-super-vl-120b-a12b`, `meta/muse-spark-1.3`, and local `ollama/qwen3:8b`; none were selected for SENSELINE trials. Installed agent versions inspected were OpenCode 2.2.5 and Codex CLI 0.164.0-alpha.11.1. The host OpenCode auth store listed OpenAI, OpenRouter, NVIDIA, and Meta profiles, but the fresh trial environment does not inherit that store; dedicated provider API-key environment variables were absent. One local Ollama model was present. There is no owner-approved spend cap or provider hard-spend limit in the experiment matrix, so the harness correctly made zero inference calls. This is a configuration and authorization blocker, not a model failure.

For future trials, the harness records the exact task instruction and prompt, trial seed, model and agent versions, sanitized profile and command, candidate source snapshot and hash, available structured agent events and stdout/stderr, per-case candidate outputs and grading reasons, runtime, usage metadata, and sandbox image digest. The JSONL transcript contains actual emitted events only; it does not request or capture private reasoning. Transcripts and run snapshots will be stored under results when trials occur.

The reproducible validation outputs are kept in [results](results/). They report reference/oracle agreement, mutation rejection, S08 unit-integrity regressions, Docker isolation attacks, and agent workspace checks. Deliberately defective controls are validation fixtures, not observed model failures. The detectable failure families include signed decoding, incompatible units, calibration order, evidence mismatch, understated uncertainty, unsafe decisions, temporal errors, and cross-layer interactions. Since model experiments were not run, there is no empirical model failure analysis; [docs/FAILURE_ANALYSIS.md](docs/FAILURE_ANALYSIS.md) states that limitation and distinguishes mutation coverage from observations.

## Runtime and cost

The local reference and grader use deterministic fixtures and make no provider calls. In this release run, `make test` passed 104 tests with zero skips in 11.73 seconds; the pytest phase of `make validate` passed 104 tests in 12.04 seconds, then validated 266 isolated reference cases and rejected all 30 mutations. The full `make validate` process took approximately 7 minutes 38 seconds on the current macOS/Docker environment. The dedicated Docker attack suite passed 12 of 12 checks with zero skips; the complete security target also resolved OpenCode 2.2.5 permissions and passed the installed Codex CLI sandbox checks. These are validation runtimes, not model performance. Model execution time and cost are NOT AVAILABLE because no inference occurred. The experiment harness records agent-reported token usage as an estimate and never labels it confirmed billing; only provider billing records can establish actual charges.

## Prior work and technical references

SENSELINE complements broad engineering and embedded-agent evaluations by testing sensor measurement meaning across a linked software pipeline. Related work includes [EngiBench](https://arxiv.org/abs/2509.17677) for engineering problem solving, [IoT-SkillsBench](https://arxiv.org/abs/2603.19583) for hardware-validated embedded and IoT tasks, [closed-loop embedded software evaluation](https://arxiv.org/abs/2610.11447), and [Vibe-FDTR](https://arxiv.org/abs/2607.28200) for agent-assisted thermal metrology. SENSELINE makes a narrow scope distinction and no first-of-kind claim; this is not an exhaustive related-work review.

Selected measurement-science sources are NIST [Technical Note 1297](https://www.nist.gov/pml/nist-technical-note-1297), the JCGM/BIPM [Guide to the Expression of Uncertainty in Measurement publications](https://www.bipm.org/en/committees/jc/jcgm/publications), NIST's [metrological traceability policy](https://www.nist.gov/metrology/metrological-traceability), ILAC [G8:09/2019](https://ilac.org/publications-and-resources/ilac-guidance-series/), and the [ISO/IEC 17025:2017 standard page](https://www.iso.org/standard/66912.html). These references inform limited synthetic task rules; inclusion does not imply general standards compliance or accreditation.

## AI-tool use and human review

Codex assisted with implementation and documentation. No model was evaluated for benchmark performance during this build. Project-owner review and independent metrology review have not been completed or claimed.

**Release status:** code, grader, and reproducibility validation are complete. Model experiments and transcript-backed failure analysis are NOT RUN because the required isolated provider credentials and approved spend controls are unavailable. The video is not published. Under the stated acceptance criteria, SENSELINE is not yet submission-ready; see [`results/submission_status.json`](results/submission_status.json).
