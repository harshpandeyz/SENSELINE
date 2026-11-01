# SENSELINE release checklist

Evidence dates: 2026-11-02. Source validation results are retained in `results/`.

## Engineering and grading

- [x] Inspect the current source, task contracts, README, Makefile, experiment configuration, retained validation results, and prior-audit findings still available in the project. Earlier narrative audit reports were absent from this checkout.
- [x] S02/S08 unit-aware grading separates numeric accuracy, unit labels, physical equivalence, and missing-unit semantic integrity. Regressions cover wrong labels, missing units, incompatible dimensions, harmless extra fields, equivalent alternate units, and wrong values with missing units.
- [x] SCR counts cases once and excludes a missing required unit by itself when the numeric value is correct; UAR uses non-ACCEPT S06/S08 cases including invalid S06 inputs without a disposition. Exact denominators and exclusions are in `docs/METHODOLOGY.md`.
- [x] S08 dimensions and processing order are explicit; 45 integration fixtures cover conversion, calibration, temperature compensation, uncertainty/covariance, boundaries, staleness, simultaneous defects, and valid end-to-end processing. Expected outputs were not changed to make implementations pass.
- [x] Independent oracle and reference solutions pass all 266 cases. All 30 mutation controls are rejected for an intended failure dimension.

## Security and reproducibility

- [x] `make test`: 104 passed, zero skipped.
- [x] `make validate`: test suite passed; 266/266 references, 30/30 mutations, eight task exports, and unit-integrity checks passed.
- [x] `make security-test`: Docker isolation tests 12/12 passed, zero skipped; Codex installed-CLI workspace and network checks passed; OpenCode 2.2.5 loaded task-local permissions and resolved shell/external-directory denies.
- [x] Candidate execution is Docker-isolated, network-disabled, non-root, read-only, resource-limited, and fail-closed. Each task export excludes hidden fixtures, graders, and reference solutions. Each trial starts in a new temporary workspace.
- [x] The OpenCode policy was resolved by the actual CLI, but dynamic denial of an OpenCode tool call was not exercised. Do not interpret policy resolution as a dynamic access test.
- [x] Clean dependency installation and tests from the final ZIP are run by `make package` through `scripts/verify_release_archive.py`; that verifier also runs reference and security checks after fresh extraction.

## Model experiment and failure analysis

- [x] Inspect OpenCode 2.2.5 and Codex CLI 0.164.0-alpha.11.1, visible provider profiles, the OpenCode model catalog, dedicated credential environment, and available local Ollama models.
- [x] `make experiment-pilot` and `make experiment-full` produce dry-run plans for 9 and 72 trials without paid API calls.
- [ ] Run the 9-trial pilot and inspect genuine transcripts.
- [ ] If the pilot is valid and approved, run the 72-trial experiment and analyze actual model failures.

Blocker: no dedicated provider API-key environment variables, selected exact model/agent matrix, owner-approved spend cap, or provider-side hard spending limit is configured. The isolated runner does not inherit host OpenCode or Codex login state. One local Ollama model is present, which does not satisfy the three-configuration experiment. No inference call was made. `results/experiment_status.json` remains `NOT RUN`; there are no model scores, costs, or transcripts.

## Documentation and submission

- [x] Root README contains scope, all eight tasks, architecture, metrics, install/run instructions, dependencies, experiment status, runtime/cost, references, disclosures, and the required video placeholder.
- [x] Methodology, related work, failure analysis, five-minute walkthrough script, independent-review package, and standalone slide deck are included. No external reviewer or public video is claimed.
- [x] `make package` creates `dist/SENSELINE_submission.zip` with README at the ZIP root and a SHA-256 sidecar; the archive verifier checks a fresh extraction, install, tests, validation, security, archive contents, and the 50 MiB limit.
- [ ] Publish the recording and replace the video placeholder with its public link.
- [ ] Complete an authorized pilot/full model experiment and transcript-backed failure analysis.

Release status: the source and validation artifact can be reproduced, but SENSELINE is **not submission-ready under the stated completion rule** until genuine model results and a public video link exist.
