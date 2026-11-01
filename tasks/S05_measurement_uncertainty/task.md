# S05 — Measurement Uncertainty Propagation

## Problem

Evaluate Type A and Type B standard uncertainties and propagate them through a linear measurement model.

## Complete specification

Provide 1..3 components. Every observation and half_width is expressed in one shared symbolic task unit `MU`; sensitivity coefficients are dimensionless, and every reported standard uncertainty is MU. `MU` is a benchmark unit label, not a claim that the measurand is SI or a particular real-world quantity. Type A component observations must contain >=2 finite decimal values; standard uncertainty of the mean is sample standard deviation (ddof=1) divided by sqrt(n). Type B kind `type_b_rectangular` supplies nonnegative symmetric half_width a; u=a/sqrt(3). Every component has a sensitivity coefficient. If correlation_matrix is omitted, and only then, use identity. If supplied, require a square n×n symmetric matrix, exact diagonal 1, coefficients in [-1,1], and positive semidefinite (all principal minors nonnegative within 1e-24). cov(i,j)=rho(i,j)*u_i*u_j. Calculate uc²=sum(c_i²u_i²)+2 sum(i<j)c_i*c_j*cov(i,j); reject materially negative variance. coverage_factor k must be finite and >0; U=k*uc. Use Decimal arithmetic, 40-digit working precision, report decimal strings. Grading tolerance: 1e-16 MU absolute for uncertainty outputs; component validity/status and list lengths are exact. Errors return {valid:false,reason:code}; codes: unsupported_component_count, type_a_requires_two_observations, negative_half_width, invalid_component_kind, invalid_correlation_shape, invalid_correlation_diagonal, invalid_correlation_matrix, non_psd_correlation_matrix, negative_propagated_variance, invalid_coverage_factor, invalid_parameters. This is the specified linear propagation model, not an assertion that all uncertainty sources in practice fit it.

## Interface

Implement exactly `def solve(payload: dict) -> dict` in `solution.py`. Input and output use JSON objects. Do not read files outside this task workspace or assume hidden-test values. Preserve explicit errors; do not silently default required parameters. Public examples and their expected outputs are in `public_examples.json`.

## Grading contract

The grader checks schema and exact validity/disposition fields, then checks every numeric field using task-specific absolute tolerances documented in the grading methodology. Invalid-input cases are part of the score. Hidden tests are deterministic and remain outside this exported workspace.
