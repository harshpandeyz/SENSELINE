# SENSELINE

## The Silent Sensor Semantics Benchmark

SENSELINE evaluates whether AI coding agents preserve the physical meaning of sensor data from raw register bytes through calibration, uncertainty, and engineering decisions. It is a deterministic software benchmark built from synthetic measurement data.

Video walkthrough: VIDEO_URL_PENDING_OWNER_UPLOAD — project owner to record and publish the five-minute walkthrough, then run `python scripts/finalize_submission.py --video-url "REAL_PUBLIC_VIDEO_FILE_URL"` to insert the public video-file URL.

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

The reference implementations are in [reference](reference/); the separate numerical oracle is in [oracle/compute.py](oracle/compute.py) and imports no reference code. [graders/grade.py](graders/grade.py) applies independent unit transforms, output schemas, exact semantic checks, and field-specific numeric tolerances. Thirty documented defective controls in [mutations](mutations/) must fail for their intended dimensions. Task export copies only the task statement, schemas, public examples, starter, and a short agent README; it excludes hidden fixtures, expected outputs, grader code, references, and mutations. Hidden grading fixtures and grader code are included in this repository and submission archive so judges can reproduce scoring; they are never copied into agent task workspaces nor mounted into candidate containers.

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

Executed 2026-11-05/06 UTC under a strict $0 API spending cap (no paid calls): 55
full-run trials plus 9 pilot trials, 24 pilot-history trials, and 3 supplementary probes
across three opencode v2.2.5 configurations —
`ollama/qwen3:8b` and `ollama/llama3.2:1b` (local inference) and
`openrouter/nvidia/nemotron-3.5-super-vl:free` (documented $0 free-tier model).
Uniform budgets: 900 s agent wall time, 5 s per-input candidate limit, 120000
tokens per trial (`configs/experiment_matrix.json`). The full run stopped by design
with QUOTA_EXHAUSTED after 55 of 72 planned trials (OpenRouter 50-request/day free
quota consumed at ~8-11 requests per agentic trial); the nemotron S04–S08 block is
missing pending the daily reset — absent, not zero. The pilot (S01/S05/S08 × 3
configurations) completed 9/9 with operator review (owner review pending).

Every trial is classified GENUINE (graded candidate code under its registered budget),
TOOL_USE (agent ran but never produced an implementation), INFRA (provider failure, no
evidence), or BUDGET_BREACH (budget enforcer cut the agent off mid-work; evidence preserved,
excluded from primary metrics).
Model metrics pool GENUINE trials only. Totals across all preserved phases (91
classified trials): 14 GENUINE, 58 TOOL_USE, 17 INFRA, 2 BUDGET_BREACH
(`results/experiment_analysis.json`, canonical; `results/experiment_status.json`
is the harness's raw trial-presence record).

Headline genuine results: nemotron full-run S01–S03, 211/216 (accuracy 0.977, SCR
0.0; the only 5 misses are reason-string vocabulary mismatches on correctly
rejected inputs). S02 and S03 perfect (120/120). Pilot S08 nemotron (genuine run
0/45, UAR 3/23) shows the core failure mode — correct arithmetic with dropped
certificate-evidence and malformed-frame rules, all silent corruption; an exploratory
budget-breach run scored 32/45 (UAR 2/23) before the enforcer cut it off. Local models
almost never engaged the file tools (qwen 0 genuine in 24 full trials, with 1/30 and
0/30 in two early attempts; llama 0 genuine; qwen2.5-coder supplementary probe 0 genuine;
beam/deepseek probes quota-blocked) — a reproducible tool-use
boundary, not a reasoning score. See docs/FAILURE_ANALYSIS.md for case-level
evidence and docs/METHODOLOGY.md for denominators and eligibility rules.

Paid frontier models were not tested: the OpenRouter account's paid credits are
exhausted (paid calls fail closed with 402), the stored OpenAI-slot key is an
OpenRouter key (invalid for OpenAI), and NVIDIA/Meta paid use has no verifiable
balance or provider-side hard limit — so no paid spend could be authorized under
the $0 cap. MuseSpark is the engineering model for this build; it was not tested
as a benchmark model (not independently runnable through the harness). Two extra
$0-pool probes (opencode/beam-free, opencode/deepseek-v4.1-flash-free) were blocked
by the shared opencode free-tier quota before producing implementations; GLM,
Nemotron-Lightning, MiMo, and Flint share the same exhausted pool and were not
attempted (see results/free_model_availability.json).

The harness records the exact task instruction and prompt, trial seed, model and
agent versions, profile and settings, candidate snapshot/hash, available
structured agent events and stdout/stderr, per-case grading outputs and reasons,
runtime, usage metadata, and sandbox image digest. The JSONL transcript contains
actual emitted events only; it does not request or capture private reasoning.

The reproducible validation outputs are kept in [results](results/). They report
reference/oracle agreement, mutation rejection, S08 unit-integrity regressions,
Docker isolation attacks, and agent workspace checks. Deliberately defective
controls are validation fixtures, not observed model failures.


## Runtime and cost

The local reference and grader use deterministic fixtures and make no provider calls. Reference validation: 266/266 isolated reference cases pass; all 30 mutation controls rejected; 8 task exports and unit-integrity checks pass. Docker security: 12/12 checks pass with zero skips; Codex CLI sandbox checks pass; OpenCode 2.2.5 permission policy resolves.

Model execution (actuals): 55 full-run trials — qwen 24 trials / 2.86 agent-hours / 136750 tokens; llama 24 trials / 0.37 agent-hours / 76163 tokens; nemotron 7 trials / 0.35 agent-hours / 268054 tokens — plus 9 pilot, 24 pilot-history, and 3 supplementary trials. Estimated cost $0 for every trial (zero-cost tier: local inference and documented $0 free-tier pricing). Confirmed billing: unverified — no paid API call was made and no billing dashboard was pulled (see reports/COST_AND_USAGE_DISCLOSURE.md for the six-way accounting); do not equate the usage-counter delta with confirmed charges. The OpenRouter account usage counter moved +$0.0016 total across all free-tier probing (4.9868 → 4.9876 → 4.9884, two +$0.0008 steps) against $5 prepaid credits (usage now ~$5.02, so paid calls fail closed with 402); free-model daily quota 50/day was exhausted twice and resets 00:00 UTC daily. The harness records agent-reported token usage as an estimate and never labels it confirmed billing; only provider billing records can establish actual charges.


## Prior work and technical references

SENSELINE complements broad engineering and embedded-agent evaluations by testing sensor measurement meaning across a linked software pipeline. Related work includes [EngiBench](https://arxiv.org/abs/2509.17677) for engineering problem solving, [IoT-SkillsBench](https://arxiv.org/abs/2603.19583) for hardware-validated embedded and IoT tasks, [closed-loop embedded software evaluation](https://arxiv.org/abs/2610.11447), and [Vibe-FDTR](https://arxiv.org/abs/2607.28200) for agent-assisted thermal metrology. SENSELINE makes a narrow scope distinction and no first-of-kind claim; this is not an exhaustive related-work review.

Selected measurement-science sources are NIST [Technical Note 1297](https://www.nist.gov/pml/nist-technical-note-1297), the JCGM/BIPM [Guide to the Expression of Uncertainty in Measurement publications](https://www.bipm.org/en/committees/jc/jcgm/publications), NIST's [metrological traceability policy](https://www.nist.gov/metrology/metrological-traceability), ILAC [G8:09/2019](https://ilac.org/publications-and-resources/ilac-guidance-series/), and the [ISO/IEC 17025:2017 standard page](https://www.iso.org/standard/66912.html). These references inform limited synthetic task rules; inclusion does not imply general standards compliance or accreditation.

## AI-tool use and human review

MuseSpark (Meta) is the engineering model for this build: it implemented the zero-cost harness extensions, the resume/quota controls, the analysis script, and this documentation. Codex assisted with the original implementation. No benchmark model was evaluated during the build itself. Pilot transcripts were reviewed by the release operator; project-owner review and independent metrology review are pending and explicitly not claimed (see results/pilot/pilot_approval.json).

**Release status:** TECHNICALLY COMPLETE — AWAITING VIDEO URL. Code, grader, security, and reproducibility validation are complete. 55/72 full-run trials plus 9 pilot, 24 pilot-history, and 3 supplementary trials (91 classified: 14 GENUINE, 58 TOOL_USE, 17 INFRA, 2 BUDGET_BREACH) executed with transcript-backed failure analysis; nemotron S04–S08 (17 slots: S03×2, S04×3, S05×3, S06×3, S07×3, S08×3) missing on free-quota exhaustion (absent, not zero) and the video is not published (`VIDEO_URL_PENDING_OWNER_UPLOAD`; finalize via `python scripts/finalize_submission.py --video-url "REAL_PUBLIC_VIDEO_FILE_URL"`). See [`results/submission_status.json`](results/submission_status.json) and [`reports/FINAL_RELEASE_AUDIT.md`](reports/FINAL_RELEASE_AUDIT.md).
