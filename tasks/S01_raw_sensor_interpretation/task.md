# S01 — Raw Sensor Interpretation

## Problem

Decode one complete fixed-width register frame into a signed or unsigned count and scaled physical value.

## Complete specification

The frame is exactly width_bits/8 bytes represented by hexadecimal text; ASCII spaces and underscores are ignored. Supported widths are 8, 16, 24, or 32 bits. byte_order is `big` or `little`. signed selects two's-complement interpretation. sentinel_codes are in-range unsigned bit-pattern values checked before signed interpretation. scale is a strictly positive exact decimal multiplier; value=count*scale. rounding_places is 0..12 and output rounding is decimal ROUND_HALF_EVEN. Reject malformed, truncated, overlong, or sentinel frames. A valid output is {valid:true,raw_count:integer,value:decimal-string}; errors are {valid:false,reason:code}. Error codes: invalid_width, invalid_byte_order, invalid_frame, frame_length, invalid_sentinels, sentinel, invalid_signed_flag, invalid_scale, invalid_parameters. No register offsets or implicit defaults are allowed except sentinel_codes defaults to [].

## Interface

Implement exactly `def solve(payload: dict) -> dict` in `solution.py`. Input and output use JSON objects. Do not read files outside this task workspace or assume hidden-test values. Preserve explicit errors; do not silently default required parameters. Public examples and their expected outputs are in `public_examples.json`.

## Grading contract

The grader checks schema and exact validity/disposition fields, then checks every numeric field using task-specific absolute tolerances documented in the grading methodology. Invalid-input cases are part of the score. Hidden tests are deterministic and remain outside this exported workspace.
