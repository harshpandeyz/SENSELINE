"""S05 — Measurement Uncertainty Propagation.

Implements solve(payload) per task.md.

Model: uc^2 = sum(c_i^2 u_i^2) + 2 sum(i<j) c_i c_j cov(i,j),
cov(i,j) = rho(i,j) u_i u_j, identity correlation when omitted.

Type A:    u = sample_std(ddof=1) / sqrt(n)
Type B rect: u = half_width / sqrt(3)

All arithmetic uses Python Decimal at 40-digit working precision; outputs are
decimal strings. Errors return {"valid": False, "reason": <code>}.
"""

import itertools
import re
from decimal import Decimal, InvalidOperation, localcontext

WORKING_PREC = 40
PSD_TOLERANCE = Decimal("1e-24")
NEGATIVE_VARIANCE_TOLERANCE = Decimal("1e-30")

_DECIMAL_RE = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")

_KIND_TYPE_A = "type_a"
_KIND_TYPE_B_RECTANGULAR = "type_b_rectangular"


def _error(code):
    return {"valid": False, "reason": code}


def _parse_decimal(value):
    """Parse a JSON number (int or plain decimal string) into a Decimal.

    Booleans and non-plain-decimal strings (exponents, NaN, etc.) are rejected
    by returning None.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        text = repr(value)
    elif isinstance(value, str):
        text = value
    else:
        return None
    if not _DECIMAL_RE.match(text):
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _validate_components(components):
    """Return (parsed, error). parsed entries: (kind, payload, sensitivity)."""
    parsed = []
    for component in components:
        if not isinstance(component, dict):
            return None, _error("invalid_parameters")
        kind = component.get("kind")
        if not isinstance(kind, str) or kind not in (
            _KIND_TYPE_A,
            _KIND_TYPE_B_RECTANGULAR,
        ):
            return None, _error("invalid_component_kind")
        sensitivity = _parse_decimal(component.get("sensitivity"))
        if sensitivity is None:
            return None, _error("invalid_parameters")
        if kind == _KIND_TYPE_A:
            observations = component.get("observations")
            if not isinstance(observations, list):
                return None, _error("invalid_parameters")
            if len(observations) < 2:
                return None, _error("type_a_requires_two_observations")
            values = []
            for observation in observations:
                value = _parse_decimal(observation)
                if value is None:
                    return None, _error("invalid_parameters")
                values.append(value)
            parsed.append((_KIND_TYPE_A, values, sensitivity))
        else:
            half_width = _parse_decimal(component.get("half_width"))
            if half_width is None:
                return None, _error("invalid_parameters")
            if half_width < 0:
                return None, _error("negative_half_width")
            parsed.append((_KIND_TYPE_B_RECTANGULAR, half_width, sensitivity))
    return parsed, None


def _determinant(matrix):
    """Exact determinant via the Leibniz permutation formula (size <= 3)."""
    size = len(matrix)
    total = Decimal(0)
    for perm in itertools.permutations(range(size)):
        inversions = 0
        for i in range(size):
            for j in range(i + 1, size):
                if perm[i] > perm[j]:
                    inversions += 1
        sign = -1 if inversions % 2 else 1
        product = Decimal(1)
        for row, col in enumerate(perm):
            product *= matrix[row][col]
        total += sign * product
    return total


def _validate_correlation(matrix, size):
    """Validate and parse the correlation matrix.

    Returns (rho, error). Checks: shape, parseability, exact unit diagonal,
    symmetry, range [-1, 1], positive semidefiniteness (principal minors).
    """
    if not isinstance(matrix, list) or len(matrix) != size:
        return None, _error("invalid_correlation_shape")
    for row in matrix:
        if not isinstance(row, list) or len(row) != size:
            return None, _error("invalid_correlation_shape")

    rho = []
    for row in matrix:
        parsed_row = []
        for entry in row:
            value = _parse_decimal(entry)
            if value is None:
                return None, _error("invalid_correlation_matrix")
            parsed_row.append(value)
        rho.append(parsed_row)

    for i in range(size):
        if rho[i][i] != 1:
            return None, _error("invalid_correlation_diagonal")

    for i in range(size):
        for j in range(i + 1, size):
            if rho[i][j] != rho[j][i]:
                return None, _error("invalid_correlation_matrix")
            if rho[i][j] < -1 or rho[i][j] > 1:
                return None, _error("invalid_correlation_matrix")

    for r in range(1, size + 1):
        for subset in itertools.combinations(range(size), r):
            sub = [[rho[i][j] for j in subset] for i in subset]
            minor = _determinant(sub)
            if minor < -PSD_TOLERANCE:
                return None, _error("non_psd_correlation_matrix")

    return rho, None


def _format_decimal(value):
    """Fixed-point decimal string (no exponent notation)."""
    return format(value, "f")


def solve(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return _error("invalid_parameters")

    components = payload.get("components")
    coverage_factor = payload.get("coverage_factor")
    if not isinstance(components, list) or coverage_factor is None:
        return _error("invalid_parameters")

    n = len(components)
    if n < 1 or n > 3:
        return _error("unsupported_component_count")

    parsed, error = _validate_components(components)
    if error:
        return error

    if "correlation_matrix" in payload:
        rho, error = _validate_correlation(payload["correlation_matrix"], n)
        if error:
            return error
    else:
        rho = [
            [Decimal(1) if i == j else Decimal(0) for j in range(n)]
            for i in range(n)
        ]

    with localcontext() as ctx:
        ctx.prec = WORKING_PREC
        sqrt3 = Decimal(3).sqrt()

        standard_uncertainties = []
        sensitivities = []
        for kind, data, sensitivity in parsed:
            sensitivities.append(sensitivity)
            if kind == _KIND_TYPE_A:
                observations = data
                count = len(observations)
                mean = sum(observations, Decimal(0)) / count
                variance = sum(
                    (x - mean) * (x - mean) for x in observations
                ) / (count - 1)
                u = variance.sqrt() / Decimal(count).sqrt()
            else:
                u = data / sqrt3
            if u == 0:
                u = Decimal(0)
            standard_uncertainties.append(u)

        combined_variance = Decimal(0)
        diagonal_part = Decimal(0)
        for i in range(n):
            term = sensitivities[i] * standard_uncertainties[i]
            diagonal_part += term * term
            combined_variance += term * term
        for i in range(n):
            for j in range(i + 1, n):
                combined_variance += (
                    Decimal(2)
                    * sensitivities[i]
                    * sensitivities[j]
                    * rho[i][j]
                    * standard_uncertainties[i]
                    * standard_uncertainties[j]
                )

        # PSD correlation makes uc^2 >= 0 mathematically; only rounding can
        # produce a tiny negative value. Reject only materially negative ones.
        if combined_variance < 0:
            tolerance = NEGATIVE_VARIANCE_TOLERANCE * max(
                Decimal(1), diagonal_part
            )
            if combined_variance < -tolerance:
                return _error("negative_propagated_variance")
            combined_variance = Decimal(0)
        combined_standard_uncertainty = combined_variance.sqrt()

        k = _parse_decimal(coverage_factor)
        if k is None or not k.is_finite() or k <= 0:
            return _error("invalid_coverage_factor")
        expanded_uncertainty = k * combined_standard_uncertainty

        return {
            "valid": True,
            "standard_uncertainties": [
                _format_decimal(u) for u in standard_uncertainties
            ],
            "combined_standard_uncertainty": _format_decimal(
                combined_standard_uncertainty
            ),
            "expanded_uncertainty": _format_decimal(expanded_uncertainty),
        }
