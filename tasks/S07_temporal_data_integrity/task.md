# S07 — Temporal and Data Integrity

## Problem

Check one timestamp and uint32 sequence number against current time and an optional last sequence.

## Complete specification

Timestamps are nonnegative integer Unix UTC milliseconds. now_ms uses the same scale. timestamp is stale only when timestamp_ms < now_ms-max_age_ms; future only when timestamp_ms > now_ms+allowed_future_skew_ms. Both boundaries are valid. age and skew must be nonnegative integers. sequence and optional last_sequence are uint32 integers. Validate required-field and timestamp/age/skew/sequence types and ranges first (invalid_timestamp_or_parameters); then check future timestamp, stale timestamp, optional last_sequence validity (invalid_last_sequence), and finally sequence disposition. Compare delta=(sequence-last_sequence) mod 2^32: delta=0 is duplicate_sequence; 1..2^31-1 is NEWER; delta=2^31 is ambiguous_half_range; 2^31+1..2^32-1 is out_of_order_sequence. Missing/null last_sequence means FIRST. Return {valid:true,reason:first_sequence|ok,sequence_order:FIRST|NEWER} or {valid:false,reason:future_timestamp|stale_timestamp|duplicate_sequence|ambiguous_half_range|out_of_order_sequence|invalid_timestamp_or_parameters|invalid_last_sequence|invalid_structure}.

## Interface

Implement exactly `def solve(payload: dict) -> dict` in `solution.py`. Input and output use JSON objects. Do not read files outside this task workspace or assume hidden-test values. Preserve explicit errors; do not silently default required parameters. Public examples and their expected outputs are in `public_examples.json`.

## Grading contract

The grader checks schema and exact validity/disposition fields, then checks every numeric field using task-specific absolute tolerances documented in the grading methodology. Invalid-input cases are part of the score. Hidden tests are deterministic and remain outside this exported workspace.
