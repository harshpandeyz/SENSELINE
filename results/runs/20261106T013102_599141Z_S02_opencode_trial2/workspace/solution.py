"""S02 — Physical Unit Integrity.

Convert only within a named physical quantity using exact contract-defined
affine transforms. Decimal input is a JSON decimal string or integer, never a
binary float. Output is rounded with ROUND_HALF_EVEN to rounding_places.
"""

import re
from decimal import Decimal, ROUND_HALF_EVEN, localcontext

_VALUE_RE = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")

# Physical quantity groups: conversion is only allowed within a group.
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

_REASON_INVALID = "invalid_parameters"
_REASON_INCOMPATIBLE = "incompatible_or_unknown_unit"


def _reject(reason):
    return {"valid": False, "reason": reason}


def _to_canonical(value: Decimal, unit: str) -> Decimal:
    if unit == "C":
        return value
    if unit == "F":
        return (value - Decimal(32)) * Decimal(5) / Decimal(9)
    if unit == "K":
        return value - Decimal("273.15")
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
    raise ValueError("unknown unit: %r" % unit)


def _from_canonical(canonical: Decimal, unit: str) -> Decimal:
    if unit == "C":
        return canonical
    if unit == "F":
        return canonical * Decimal(9) / Decimal(5) + Decimal(32)
    if unit == "K":
        return canonical + Decimal("273.15")
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
    raise ValueError("unknown unit: %r" % unit)


def solve(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return _reject(_REASON_INVALID)

    # Required parameters are never silently defaulted.
    for key in ("value", "from_unit", "to_unit", "rounding_places"):
        if key not in payload:
            return _reject(_REASON_INVALID)

    raw_value = payload["value"]
    if isinstance(raw_value, bool) or not isinstance(raw_value, (str, int)):
        return _reject(_REASON_INVALID)
    if isinstance(raw_value, str):
        if not _VALUE_RE.match(raw_value):
            return _reject(_REASON_INVALID)
        try:
            value = Decimal(raw_value)
        except Exception:
            return _reject(_REASON_INVALID)
    else:
        value = Decimal(raw_value)

    rounding_places = payload["rounding_places"]
    if isinstance(rounding_places, bool) or not isinstance(rounding_places, int):
        return _reject(_REASON_INVALID)
    if rounding_places < 0 or rounding_places > 12:
        return _reject(_REASON_INVALID)

    from_unit = payload["from_unit"]
    to_unit = payload["to_unit"]
    from_group = _UNIT_GROUP.get(from_unit) if isinstance(from_unit, str) else None
    to_group = _UNIT_GROUP.get(to_unit) if isinstance(to_unit, str) else None
    if from_group is None or to_group is None or from_group != to_group:
        return _reject(_REASON_INCOMPATIBLE)

    with localcontext() as ctx:
        ctx.prec = 50
        canonical = _to_canonical(value, from_unit)
        result = _from_canonical(canonical, to_unit)
        quantized = result.quantize(
            Decimal(1).scaleb(-rounding_places), rounding=ROUND_HALF_EVEN
        )
        # Normalize negative zero to plain zero.
        if quantized == 0:
            quantized = abs(quantized)
        output_value = format(quantized, "f")

    return {"valid": True, "value": output_value, "unit": to_unit}
