"""S05 — Measurement Uncertainty Propagation.

Implements solve(payload) per the task specification using Decimal
arithmetic at 40-digit working precision, reporting decimal strings.
"""

from decimal import Decimal, InvalidOperation, getcontext
from itertools import combinations

WORKING_PREC = 40
PSD_TOLERANCE = Decimal("1e-24")
VARIANCE_TOLERANCE = Decimal("1e-24")

VALID_KINDS = ("type_a", "type_b_rectangular")
ONE = Decimal(1)
TWO = Decimal(2)
THREE = Decimal(3)

# 40-digit working precision for every Decimal operation below.
getcontext().prec = WORKING_PREC


def _reject(code):
    return {"valid": False, "reason": code}


def _parse_decimal(value):
    """Parse a finite decimal from JSON-compatible input.

    Returns a Decimal, or None when the value is missing, not a decimal,
    or non-finite.
    """
    if value is None or isinstance(value, bool):
        return None
    text = value.strip() if isinstance(value, str) else str(value)
    try:
        result = Decimal(text)
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not result.is_finite():
        return None
    return result


def _format_decimal(value):
    """Format a Decimal as a plain decimal string (no exponent notation)."""
    text = format(value.normalize(), "f")
    if text.startswith("-") and all(c in "-0." for c in text):
        text = "0"
    if text == "" or text == "-":
        text = "0"
    return text


def _determinant(matrix):
    """Exact determinant of a 1x1, 2x2 or 3x3 Decimal matrix."""
    size = len(matrix)
    if size == 1:
        return matrix[0][0]
    if size == 2:
        a, b = matrix[0]
        c, d = matrix[1]
        return a * d - b * c
    (a, b, c), (d, e, f), (g, h, i) = matrix
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def solve(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return _reject("invalid_parameters")

    components = payload.get("components")
    if not isinstance(components, list):
        return _reject("invalid_parameters")

    n_components = len(components)
    if n_components < 1 or n_components > 3:
        return _reject("unsupported_component_count")

    standard_uncertainties = []
    sensitivities = []

    for component in components:
        if not isinstance(component, dict):
            return _reject("invalid_parameters")

        kind = component.get("kind")
        if kind not in VALID_KINDS:
            return _reject("invalid_component_kind")

        sensitivity = _parse_decimal(component.get("sensitivity"))
        if sensitivity is None:
            return _reject("invalid_parameters")

        if kind == "type_a":
            observations = component.get("observations")
            if not isinstance(observations, list):
                return _reject("invalid_parameters")
            if len(observations) < 2:
                return _reject("type_a_requires_two_observations")
            values = []
            for observation in observations:
                value = _parse_decimal(observation)
                if value is None:
                    return _reject("invalid_parameters")
                values.append(value)
            count = Decimal(len(values))
            mean = sum(values, Decimal(0)) / count
            variance = sum((x - mean) ** 2 for x in values) / (count - ONE)
            # Standard uncertainty of the mean: s / sqrt(n), ddof=1.
            standard_uncertainties.append(variance.sqrt() / count.sqrt())
        else:  # type_b_rectangular
            half_width = _parse_decimal(component.get("half_width"))
            if half_width is None:
                return _reject("invalid_parameters")
            if half_width < 0:
                return _reject("negative_half_width")
            # Symmetric rectangular distribution: u = a / sqrt(3).
            standard_uncertainties.append(half_width / THREE.sqrt())

        sensitivities.append(sensitivity)

    # Correlation matrix: identity when omitted, validated otherwise.
    rho = [[ONE if i == j else Decimal(0) for j in range(n_components)]
           for i in range(n_components)]
    if "correlation_matrix" in payload:
        matrix = payload.get("correlation_matrix")
        if (
            not isinstance(matrix, list)
            or len(matrix) != n_components
            or any(
                not isinstance(row, list) or len(row) != n_components
                for row in matrix
            )
        ):
            return _reject("invalid_correlation_shape")
        for i in range(n_components):
            for j in range(n_components):
                value = _parse_decimal(matrix[i][j])
                if value is None:
                    return _reject("invalid_correlation_matrix")
                rho[i][j] = value
        for i in range(n_components):
            if rho[i][i] != ONE:
                return _reject("invalid_correlation_diagonal")
        for i in range(n_components):
            for j in range(n_components):
                if rho[i][j] != rho[j][i]:
                    return _reject("invalid_correlation_matrix")
                if rho[i][j] < -ONE or rho[i][j] > ONE:
                    return _reject("invalid_correlation_matrix")
        # Positive semidefinite: all principal minors non-negative
        # within the working tolerance.
        for size in range(1, n_components + 1):
            for indices in combinations(range(n_components), size):
                sub = [[rho[i][j] for j in indices] for i in indices]
                minor = _determinant(sub)
                if minor < -PSD_TOLERANCE:
                    return _reject("non_psd_correlation_matrix")

    coverage = _parse_decimal(payload.get("coverage_factor"))
    if coverage is None or coverage <= 0:
        return _reject("invalid_coverage_factor")

    # Propagate through the linear measurement model.
    combined_variance = Decimal(0)
    scale = Decimal(0)
    for i in range(n_components):
        term = sensitivities[i] ** 2 * standard_uncertainties[i] ** 2
        combined_variance += term
        scale += term
    for i in range(n_components):
        for j in range(i + 1, n_components):
            combined_variance += (
                TWO
                * sensitivities[i]
                * sensitivities[j]
                * rho[i][j]
                * standard_uncertainties[i]
                * standard_uncertainties[j]
            )
    # Reject materially negative variance; silence roundoff-level noise.
    if combined_variance < 0:
        tolerance = VARIANCE_TOLERANCE * max(ONE, scale)
        if combined_variance < -tolerance:
            return _reject("negative_propagated_variance")
        combined_variance = Decimal(0)

    combined_standard_uncertainty = combined_variance.sqrt()
    expanded_uncertainty = coverage * combined_standard_uncertainty

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
