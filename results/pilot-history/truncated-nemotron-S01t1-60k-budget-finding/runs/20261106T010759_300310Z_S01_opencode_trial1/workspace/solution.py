"""S01 — Raw Sensor Interpretation.

Decodes one fixed-width register frame into a signed/unsigned count and a
scaled physical value, per task.md.
"""

import re

_SUPPORTED_WIDTHS = (8, 16, 24, 32)
_BYTE_ORDERS = ("big", "little")
_REQUIRED_KEYS = (
    "frame_hex",
    "width_bits",
    "byte_order",
    "signed",
    "scale",
    "rounding_places",
)
_ALLOWED_KEYS = set(_REQUIRED_KEYS) | {"sentinel_codes"}

_HEX_RE = re.compile(r"^[0-9a-fA-F]*$")
_SCALE_RE = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")


def _error(reason: str) -> dict:
    return {"valid": False, "reason": reason}


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_scale(value):
    """Return (coefficient, exponent) so that scale = coefficient * 10**-exponent,
    or None when scale is not a strictly positive exact decimal."""
    if _is_int(value):
        return (value, 0) if value > 0 else None
    if isinstance(value, str) and _SCALE_RE.match(value):
        if "." in value:
            whole, frac = value.split(".")
            coefficient = int(whole + frac)
            exponent = len(frac)
        else:
            coefficient = int(value)
            exponent = 0
        if coefficient > 0:
            return (coefficient, exponent)
    return None


def solve(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return _error("invalid_parameters")

    for key in payload:
        if key not in _ALLOWED_KEYS:
            return _error("invalid_parameters")
    for key in _REQUIRED_KEYS:
        if key not in payload:
            return _error("invalid_parameters")

    width = payload["width_bits"]
    if not _is_int(width) or width not in _SUPPORTED_WIDTHS:
        return _error("invalid_width")

    byte_order = payload["byte_order"]
    if byte_order not in _BYTE_ORDERS:
        return _error("invalid_byte_order")

    signed = payload["signed"]
    if not isinstance(signed, bool):
        return _error("invalid_signed_flag")

    scale = _parse_scale(payload["scale"])
    if scale is None:
        return _error("invalid_scale")

    places = payload["rounding_places"]
    if not _is_int(places) or places < 0 or places > 12:
        return _error("invalid_parameters")

    sentinel_codes = payload.get("sentinel_codes", [])
    max_unsigned = (1 << width) - 1
    if not isinstance(sentinel_codes, list):
        return _error("invalid_sentinels")
    sentinels = set()
    for code in sentinel_codes:
        if not _is_int(code) or code < 0 or code > max_unsigned:
            return _error("invalid_sentinels")
        sentinels.add(code)

    frame_hex = payload["frame_hex"]
    if not isinstance(frame_hex, str):
        return _error("invalid_frame")
    cleaned = frame_hex.replace(" ", "").replace("_", "")
    if not _HEX_RE.match(cleaned):
        return _error("invalid_frame")
    if len(cleaned) % 2 != 0:
        return _error("invalid_frame")
    try:
        raw_bytes = bytes.fromhex(cleaned)
    except ValueError:
        return _error("invalid_frame")

    needed = width // 8
    if len(raw_bytes) != needed:
        return _error("frame_length")

    unsigned = int.from_bytes(raw_bytes, byte_order)
    if unsigned in sentinels:
        return _error("sentinel")

    if signed and unsigned >= (1 << (width - 1)):
        raw_count = unsigned - (1 << width)
    else:
        raw_count = unsigned

    # Exact value = raw_count * scale; scale = coef * 10**-exp.
    coef, exp = scale
    numerator = raw_count * coef  # value * 10**exp (exact integer)
    shift = places - exp  # value * 10**places = numerator * 10**shift

    if shift >= 0:
        scaled = numerator * (10 ** shift)
    else:
        denom = 10 ** (-shift)
        magnitude = numerator if numerator >= 0 else -numerator
        quotient, remainder = divmod(magnitude, denom)
        twice = remainder * 2
        if twice > denom or (twice == denom and (quotient & 1)):
            quotient += 1
        scaled = quotient if numerator >= 0 else -quotient

    # Format scaled / 10**places with exactly `places` fractional digits.
    if places > 0:
        unit = 10 ** places
        sign = "-" if scaled < 0 else ""
        magnitude = scaled if scaled >= 0 else -scaled
        whole = magnitude // unit
        fraction = magnitude % unit
        value = f"{sign}{whole}.{fraction:0{places}d}"
    else:
        sign = "-" if scaled < 0 else ""
        magnitude = scaled if scaled >= 0 else -scaled
        value = f"{sign}{magnitude}"

    return {"valid": True, "raw_count": raw_count, "value": value}
