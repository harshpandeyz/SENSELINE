"""S01 — Raw Sensor Interpretation.

Decode one complete fixed-width register frame into a signed or unsigned
count and a scaled physical value. Implements solve(payload) -> dict.
"""

import re
from decimal import Decimal, ROUND_HALF_EVEN, InvalidOperation, localcontext

_SUPPORTED_WIDTHS = (8, 16, 24, 32)
_HEX_DIGITS = set("0123456789abcdefABCDEF")
_SCALE_PATTERN = re.compile(r"-?[0-9]+(\.[0-9]+)?")
# Working precision for exact decimal arithmetic (count <= 2^32-1 is 10 digits,
# so 100 significant digits is more than enough for any realistic scale).
_WORK_PREC = 100


def _is_int(value):
    """True for integers only (JSON booleans are excluded)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_scale(scale):
    """Return a Decimal for an exact positive decimal, or None if invalid."""
    if isinstance(scale, bool):
        return None
    if isinstance(scale, int):
        return Decimal(scale)
    if isinstance(scale, str):
        if not _SCALE_PATTERN.fullmatch(scale):
            return None
        try:
            return Decimal(scale)
        except InvalidOperation:
            return None
    return None


def solve(payload: dict) -> dict:
    # 1. width_bits (required; must be one of 8/16/24/32)
    width = payload.get("width_bits")
    if not _is_int(width) or width not in _SUPPORTED_WIDTHS:
        return {"valid": False, "reason": "invalid_width"}

    # 2. byte_order (required)
    byte_order = payload.get("byte_order")
    if byte_order not in ("big", "little"):
        return {"valid": False, "reason": "invalid_byte_order"}

    # 3. frame_hex (required) -> malformed text is invalid_frame
    frame_hex = payload.get("frame_hex")
    if not isinstance(frame_hex, str):
        return {"valid": False, "reason": "invalid_frame"}
    cleaned = frame_hex.replace(" ", "").replace("_", "")
    if (
        not cleaned
        or len(cleaned) % 2 != 0
        or any(c not in _HEX_DIGITS for c in cleaned)
    ):
        return {"valid": False, "reason": "invalid_frame"}
    try:
        raw_bytes = bytes.fromhex(cleaned)
    except ValueError:
        return {"valid": False, "reason": "invalid_frame"}

    # 4. frame length must exactly match width_bits/8 bytes
    if len(raw_bytes) != width // 8:
        return {"valid": False, "reason": "frame_length"}

    # 5. sentinel_codes parameter (defaults to [])
    max_count = (1 << width) - 1
    sentinel_codes = payload.get("sentinel_codes", [])
    if not isinstance(sentinel_codes, list):
        return {"valid": False, "reason": "invalid_sentinels"}
    sentinel_set = set()
    for code in sentinel_codes:
        if not _is_int(code) or code < 0 or code > max_count:
            return {"valid": False, "reason": "invalid_sentinels"}
        sentinel_set.add(code)

    # 6. unsigned bit-pattern count; sentinels are checked before signed
    #    interpretation, on the raw unsigned value.
    count = int.from_bytes(raw_bytes, byte_order)
    if count in sentinel_set:
        return {"valid": False, "reason": "sentinel"}

    # 7. signed flag (required)
    signed = payload.get("signed")
    if not isinstance(signed, bool):
        return {"valid": False, "reason": "invalid_signed_flag"}

    # 8. scale (required): strictly positive exact decimal
    scale = payload.get("scale")
    scale_decimal = _parse_scale(scale)
    if scale_decimal is None or scale_decimal <= 0:
        return {"valid": False, "reason": "invalid_scale"}

    # 9. rounding_places (required): integer in 0..12
    rounding_places = payload.get("rounding_places")
    if not _is_int(rounding_places) or not (0 <= rounding_places <= 12):
        return {"valid": False, "reason": "invalid_parameters"}

    # 10. two's-complement signed interpretation
    if signed and count >= (1 << (width - 1)):
        count -= 1 << width

    # 11. value = count * scale, rounded to rounding_places (ROUND_HALF_EVEN)
    with localcontext() as ctx:
        ctx.prec = _WORK_PREC
        scaled = Decimal(count) * scale_decimal
        quantum = Decimal(1).scaleb(-rounding_places)
        rounded = scaled.quantize(quantum, rounding=ROUND_HALF_EVEN)

    # Normalize negative zero to a plain zero value string.
    if rounded == 0:
        rounded = rounded.copy_abs()
    value_str = format(rounded, "f")

    return {"valid": True, "raw_count": count, "value": value_str}
