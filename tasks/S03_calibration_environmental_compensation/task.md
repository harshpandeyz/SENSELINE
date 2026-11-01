# S03 — Calibration and Environmental Compensation

## Problem

Apply the declared affine calibration and temperature compensation exactly once.

## Complete specification

Compute corrected = gain*raw_value + offset + temp_coefficient*(ambient_temperature_c-reference_temperature_c), in that order. This task uses the explicit symbolic measurand unit `MU`: raw_value, offset, and corrected_value are MU; temp_coefficient is MU/°C; both temperatures are °C; gain is dimensionless. `MU` is a benchmark unit label, not a claim that the quantity is SI or a particular real-world unit. All coefficients and inputs are exact decimal strings or integers. correction_state must equal RAW; any other state is rejected as already_corrected. Coefficients are all required, finite; no defaults. Output rounds by ROUND_HALF_EVEN to rounding_places 0..12. Return {valid:false,reason:already_corrected} for another correction state, invalid_gain for gain<=0, and invalid_parameters for malformed, missing, or nonfinite values or precision.

## Interface

Implement exactly `def solve(payload: dict) -> dict` in `solution.py`. Input and output use JSON objects. Do not read files outside this task workspace or assume hidden-test values. Preserve explicit errors; do not silently default required parameters. Public examples and their expected outputs are in `public_examples.json`.

## Grading contract

The grader checks schema and exact validity/disposition fields, then checks every numeric field using task-specific absolute tolerances documented in the grading methodology. Invalid-input cases are part of the score. Hidden tests are deterministic and remain outside this exported workspace.
