# S06 — Conformity and Engineering Decisions

## Problem

Apply the specified conservative interval decision rule, including equality boundaries.

## Complete specification

Given finite decimal y, expanded_uncertainty U, lower_limit L and upper_limit H, require U>=0 and L<=H. All four values use the same explicit symbolic task unit `MU`; this label is not a claim that the measured quantity is SI or a particular real-world unit. Form [y-U,y+U]. ACCEPT iff y-U>=L and y+U<=H; REJECT iff y+U<L or y-U>H (strict disjointness); otherwise INDETERMINATE. Thus equality at both specification limits is ACCEPT when the complete interval remains inside; an uncertainty interval merely touching a limit from outside is INDETERMINATE. Never substitute another guard-band rule. Return valid, interval endpoints, and one exact decision string. Errors return {valid:false,reason:negative_uncertainty|malformed_limits|invalid_parameters}.

## Interface

Implement exactly `def solve(payload: dict) -> dict` in `solution.py`. Input and output use JSON objects. Do not read files outside this task workspace or assume hidden-test values. Preserve explicit errors; do not silently default required parameters. Public examples and their expected outputs are in `public_examples.json`.

## Grading contract

The grader checks schema and exact validity/disposition fields, then checks every numeric field using task-specific absolute tolerances documented in the grading methodology. Invalid-input cases are part of the score. Hidden tests are deterministic and remain outside this exported workspace.
