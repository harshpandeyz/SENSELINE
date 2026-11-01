# S04 — Calibration Applicability and Validity

## Problem

Check whether synthetic calibration evidence applies to one measurement under explicit task rules.

## Complete specification

Check serial, measurand, CURRENT status, exact YYYY-MM-DD validity dates (inclusive), inclusive measurement range, finite nonnegative uncertainty, exact unit, and DOCUMENTED traceability. Collect every independently checkable reason in fixed order: missing certificate fields in serial_number, measurand, status, valid_from, valid_to, range_min, range_max, uncertainty, unit, traceability_chain_status order; serial_mismatch; measurand_mismatch; calibration_not_current; invalid_validity_interval; outside_validity_dates; invalid_date; invalid_range; outside_calibration_range; invalid_range_or_value; invalid_uncertainty or missing_or_invalid_uncertainty; unit_mismatch; traceability_not_documented. Skip checks requiring absent certificate values; a separately malformed measurement date/value remains reportable. A missing certificate field is not duplicated as malformed. Malformed outer objects return invalid_structure. DOCUMENTED is synthetic evidence only and establishes neither accreditation nor legal compliance.

## Interface

Implement exactly `def solve(payload: dict) -> dict` in `solution.py`. Input and output use JSON objects. Do not read files outside this task workspace or assume hidden-test values. Preserve explicit errors; do not silently default required parameters. Public examples and their expected outputs are in `public_examples.json`.

## Grading contract

The grader checks schema and exact validity/disposition fields, then checks every numeric field using task-specific absolute tolerances documented in the grading methodology. Invalid-input cases are part of the score. Hidden tests are deterministic and remain outside this exported workspace.
