"""S02 — Physical Unit Integrity.

Convert only within a named physical quantity using exact contract-defined
affine transforms. All arithmetic uses decimal.Decimal so inputs stay exact
decimals (no binary floats).
"""

import re
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext

_UNIT_CATEGORY = {
    "C": "temperature",
    "F": "temperature",
    "K": "temperature",
    "Pa": "pressure",
    "kPa": "pressure",
    "bar": "pressure",
    "V": "voltage",
    "mV": "voltage",
}

_DECIMAL_RE = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")

_ERROR_INVALID = {"valid": False, "reason": "invalid_parameters"}
_ERROR_INCOMPATIBLE = {
    "valid": False,
    "reason": "incompatible_or_unknown_unit",
}


def _to_canonical(unit, x):
    """Convert from `unit` to the canonical unit of its quantity."""
    if unit == "C":
        return x
    if unit == "F":
        return (x - Decimal(32)) * Decimal(5) / Decimal(9)
    if unit == "K":
        return x - Decimal("273.15")
    if unit == "Pa":
        return x
    if unit == "kPa":
        return x * Decimal(1000)
    if unit == "bar":
        return x * Decimal(100000)
    if unit == "V":
        return x
    if unit == "mV":
        return x / Decimal(1000)
    raise AssertionError("unknown unit: %r" % (unit,))


def _from_canonical(unit, x):
    """Convert from the canonical unit of its quantity to `unit`."""
    if unit == "C":
        return x
    if unit == "F":
        return x * Decimal(9) / Decimal(5) + Decimal(32)
    if unit == "K":
        return x + Decimal("273.15")
    if unit == "Pa":
        return x
    if unit == "kPa":
        return x / Decimal(1000)
    if unit == "bar":
        return x / Decimal(100000)
    if unit == "V":
        return x
    if unit == "mV":
        return x * Decimal(1000)
    raise AssertionError("unknown unit: %r" % (unit,))


def solve(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return _ERROR_INVALID

    try:
        value = payload["value"]
        from_unit = payload["from_unit"]
        to_unit = payload["to_unit"]
        rounding_places = payload["rounding_places"]
    except (KeyError, TypeError):
        # Required parameters must be present; never silently default them.
        return _ERROR_INVALID

    # ---- validate value: JSON decimal string or integer, not binary float ----
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return _ERROR_INVALID
    if isinstance(value, str) and not _DECIMAL_RE.fullmatch(value):
        return _ERROR_INVALID
    dec = Decimal(value)

    # ---- validate rounding_places: integer in 0..12 ----
    if isinstance(rounding_places, bool) or not isinstance(rounding_places, int):
        return _ERROR_INVALID
    if rounding_places < 0 or rounding_places > 12:
        return _ERROR_INVALID

    # ---- validate units: known and compatible (same physical quantity) ----
    if from_unit not in _UNIT_CATEGORY or to_unit not in _UNIT_CATEGORY:
        return _ERROR_INCOMPATIBLE
    if _UNIT_CATEGORY[from_unit] != _UNIT_CATEGORY[to_unit]:
        return _ERROR_INCOMPATIBLE

    # ---- convert with sufficient decimal precision ----
    _sign, _digits, _exp = dec.as_tuple()
    sig_digits = len(_digits)
    # Account for integer magnitude (e.g. "100000..." has few digits but many
    # integer positions), which the quantized result must preserve.
    magnitude_digits = sig_digits + _exp if _exp > 0 else sig_digits
    prec = max(80, magnitude_digits + rounding_places + 25)
    quantum = Decimal(10) ** (-rounding_places)
    with localcontext() as ctx:
        ctx.prec = prec
        if from_unit == to_unit:
            result = dec  # same-unit conversion is identity
        else:
            result = _from_canonical(to_unit, _to_canonical(from_unit, dec))
        for _ in range(4):
            try:
                result = result.quantize(quantum, rounding=ROUND_HALF_EVEN)
                break
            except InvalidOperation:
                ctx.prec *= 2  # give the quantized coefficient room to fit
        else:
            return _ERROR_INVALID
        if result == 0:
            result = result.copy_abs()  # normalize -0.00 -> 0.00, keep exponent

    return {
        "valid": True,
        "value": format(result, "f"),
        "unit": to_unit,
    }
