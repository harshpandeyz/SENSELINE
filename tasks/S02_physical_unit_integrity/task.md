# S02 — Physical Unit Integrity

## Problem

Convert only within a named physical quantity using exact contract-defined affine transforms.

## Complete specification

Supported temperature units are C, F, K; pressure units Pa, kPa, bar; voltage units V, mV. Convert source to canonical C/Pa/V and then target. Exact definitions: F→C=(F−32)*5/9, K→C=K−273.15; kPa→Pa=1000*kPa, bar→Pa=100000*bar; mV→V=mV/1000. Reverse transforms are algebraic inverses. Same-unit conversion is identity. Never infer units; reject unknown or incompatible pairs. Decimal input is a JSON decimal string or integer, not binary float. Output is rounded to rounding_places (0..12) using ROUND_HALF_EVEN and includes the requested unit. Return {valid:false,reason:incompatible_or_unknown_unit} for unknown/incompatible units and invalid_parameters for malformed decimals or precision.

## Interface

Implement exactly `def solve(payload: dict) -> dict` in `solution.py`. Input and output use JSON objects. Do not read files outside this task workspace or assume hidden-test values. Preserve explicit errors; do not silently default required parameters. Public examples and their expected outputs are in `public_examples.json`.

## Grading contract

The grader checks schema and exact validity/disposition fields, then checks every numeric field using task-specific absolute tolerances documented in the grading methodology. Invalid-input cases are part of the score. Hidden tests are deterministic and remain outside this exported workspace.
