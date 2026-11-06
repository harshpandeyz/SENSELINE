"""S02 — Physical Unit Integrity.

Convert only within a named physical quantity using exact contract-defined
affine transforms. All arithmetic is performed with ``decimal.Decimal`` so
inputs are treated as decimal numbers, never binary floats.
"""

import re
from decimal import Decimal, localcontext, ROUND_HALF_EVEN

_UNIT_GROUP = {
    "C": "temperature",
    "F": "temperature",
    "K": "temperature",
    "Pa": "pressure",
    "kPa": "pressure",
    "bar": "pressure",
    "V": "voltage",
    "mV": "voltage",
}

_VALUE_RE = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")
_K_OFFSET = Decimal("273.15")


def _to_canonical(unit, value):
    """Convert a value from *unit* to the quantity's canonical unit."""
    if unit == "C":
        return value
    if unit == "F":
        return (value - Decimal(32)) * Decimal(5) / Decimal(9)
    if unit == "K":
        return value - _K_OFFSET
    if unit == "Pa":
        return value
    if unit == "kPa":
        return value * Decimal(1000)
    if unit == "bar":
        return value * Decimal(100000)
    if unit == "V":
        return value
    if unit == "mV":
        return value / Decimal(1000)
    raise ValueError("unknown unit: %r" % (unit,))


def _from_canonical(unit, canonical):
    """Convert a canonical value to *unit*."""
    if unit == "C":
        return canonical
    if unit == "F":
        return canonical * Decimal(9) / Decimal(5) + Decimal(32)
    if unit == "K":
        return canonical + _K_OFFSET
    if unit == "Pa":
        return canonical
    if unit == "kPa":
        return canonical / Decimal(1000)
    if unit == "bar":
        return canonical / Decimal(100000)
    if unit == "V":
        return canonical
    if unit == "mV":
        return canonical * Decimal(1000)
    raise ValueError("unknown unit: %r" % (unit,))


def solve(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {"valid": False, "reason": "invalid_parameters"}

    # Required parameters must be present explicitly; never silently default.
    for key in ("value", "from_unit", "to_unit", "rounding_places"):
        if key not in payload:
            return {"valid": False, "reason": "invalid_parameters"}

    value = payload["value"]
    from_unit = payload["from_unit"]
    to_unit = payload["to_unit"]
    rounding_places = payload["rounding_places"]

    # Units must be known and belong to the same physical quantity.
    if (
        not isinstance(from_unit, str)
        or not isinstance(to_unit, str)
        or from_unit not in _UNIT_GROUP
        or to_unit not in _UNIT_GROUP
        or _UNIT_GROUP[from_unit] != _UNIT_GROUP[to_unit]
    ):
        return {"valid": False, "reason": "incompatible_or_unknown_unit"}

    # Decimal input: a JSON decimal string or an integer, never a binary float.
    if isinstance(value, bool) or isinstance(value, float):
        return {"valid": False, "reason": "invalid_parameters"}
    if isinstance(value, int):
        decimal_value = Decimal(value)
    elif isinstance(value, str) and _VALUE_RE.fullmatch(value):
        decimal_value = Decimal(value)
    else:
        return {"valid": False, "reason": "invalid_parameters"}

    # Precision: an integer in [0, 12].
    if isinstance(rounding_places, bool) or not isinstance(rounding_places, int):
        return {"valid": False, "reason": "invalid_parameters"}
    if rounding_places < 0 or rounding_places > 12:
        return {"valid": False, "reason": "invalid_parameters"}

    # Convert source -> canonical -> target with ample working precision.
    digit_count = len(decimal_value.as_tuple().digits)
    work_prec = max(100, digit_count + rounding_places + 20)
    with localcontext() as ctx:
        ctx.prec = work_prec
        canonical = _to_canonical(from_unit, decimal_value)
        result = _from_canonical(to_unit, canonical)
        quantum = Decimal(1).scaleb(-rounding_places)
        result = result.quantize(quantum, rounding=ROUND_HALF_EVEN)

    # Normalise negative zero to positive zero.
    if result == 0:
        result = abs(result)

    return {"valid": True, "value": format(result, "f"), "unit": to_unit}
