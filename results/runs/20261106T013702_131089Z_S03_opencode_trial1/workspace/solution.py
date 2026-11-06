"""S03 — Calibration and Environmental Compensation.

Apply the declared affine calibration and temperature compensation exactly once:

    corrected = gain*raw_value + offset + temp_coefficient*
                (ambient_temperature_c - reference_temperature_c)

All inputs are exact decimal strings or integers; the unit label is `MU`.
Output rounds once with ROUND_HALF_EVEN to rounding_places (0..12).
"""

import re
from decimal import Decimal, ROUND_HALF_EVEN, localcontext

_NUMERIC_PATTERN = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")

_NUMERIC_FIELDS = (
    "raw_value",
    "gain",
    "offset",
    "temp_coefficient",
    "ambient_temperature_c",
    "reference_temperature_c",
)


def _invalid(reason):
    return {"valid": False, "reason": reason}


def _parse_decimal(value):
    """Parse an accepted numeric input to a Decimal, or None if malformed."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str) and _NUMERIC_PATTERN.match(value):
        return Decimal(value)
    return None


def _working_precision(values):
    """Context precision large enough for all intermediate results to be exact."""
    total = 0
    for v in values.values():
        t = v.as_tuple()
        total += len(t.digits) + abs(t.exponent)
    return max(60, total * 2 + 20)


def solve(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return _invalid("invalid_parameters")

    # Structural validation: every required field present and well-formed.
    values = {}
    for key in _NUMERIC_FIELDS:
        if key not in payload:
            return _invalid("invalid_parameters")
        parsed = _parse_decimal(payload[key])
        if parsed is None:
            return _invalid("invalid_parameters")
        values[key] = parsed

    if ("correction_state" not in payload
            or not isinstance(payload["correction_state"], str)):
        return _invalid("invalid_parameters")

    places = payload.get("rounding_places")
    if (isinstance(places, bool) or not isinstance(places, int)
            or places < 0 or places > 12):
        return _invalid("invalid_parameters")

    # State must equal RAW; any other state is already_corrected.
    if payload["correction_state"] != "RAW":
        return _invalid("already_corrected")

    # Gain must be positive.
    if values["gain"] <= 0:
        return _invalid("invalid_gain")

    # Exact affine computation, rounded once with ROUND_HALF_EVEN.
    with localcontext() as ctx:
        ctx.prec = _working_precision(values)
        corrected = (values["gain"] * values["raw_value"]
                     + values["offset"]
                     + values["temp_coefficient"]
                     * (values["ambient_temperature_c"]
                        - values["reference_temperature_c"]))
        corrected = corrected.quantize(
            Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)
        # Normalise negative zero to plain zero.
        if corrected == 0:
            corrected = corrected.copy_abs()

    return {"valid": True, "corrected_value": str(corrected)}
