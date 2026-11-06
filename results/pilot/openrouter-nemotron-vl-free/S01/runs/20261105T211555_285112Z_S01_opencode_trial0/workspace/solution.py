"""Decode one fixed-width register frame into a signed/unsigned count and scaled value.

Implements the S01 — Raw Sensor Interpretation task contract.
See task.md for the full specification.
"""

import re
from decimal import Decimal, ROUND_HALF_EVEN, localcontext

_MISSING = object()

_VALID_WIDTHS = (8, 16, 24, 32)
_HEX_RE = re.compile(r"[0-9a-fA-F]+\Z")
_SCALE_RE = re.compile(r"[0-9]+(\.[0-9]+)?\Z")


def _error(code):
    return {"valid": False, "reason": code}


def solve(payload: dict) -> dict:
    # --- 1. width_bits (required, must be one of 8/16/24/32) ---
    width = payload.get("width_bits", _MISSING)
    if type(width) is not int or width not in _VALID_WIDTHS:
        return _error("invalid_width")

    # --- 2. byte_order ---
    byte_order = payload.get("byte_order", _MISSING)
    if byte_order not in ("big", "little"):
        return _error("invalid_byte_order")

    # --- 3. signed (must be a real boolean) ---
    signed = payload.get("signed", _MISSING)
    if type(signed) is not bool:
        return _error("invalid_signed_flag")

    # --- 4. scale (strictly positive exact decimal; int or decimal string) ---
    scale_raw = payload.get("scale", _MISSING)
    if type(scale_raw) is bool or type(scale_raw) not in (int, str):
        return _error("invalid_scale")
    scale_text = str(scale_raw) if type(scale_raw) is int else scale_raw
    if not _SCALE_RE.fullmatch(scale_text):
        return _error("invalid_scale")
    scale_dec = Decimal(scale_text)
    if scale_dec <= 0:
        return _error("invalid_scale")

    # --- 5. rounding_places (integer 0..12) ---
    places = payload.get("rounding_places", _MISSING)
    if type(places) is not int or not (0 <= places <= 12):
        return _error("invalid_parameters")

    # --- 6. sentinel_codes (defaults to []; in-range unsigned patterns) ---
    sentinel_raw = payload.get("sentinel_codes", _MISSING)
    sentinels = [] if sentinel_raw is _MISSING else sentinel_raw
    max_count = (1 << width) - 1
    if not isinstance(sentinels, list):
        return _error("invalid_sentinels")
    for code in sentinels:
        if type(code) is not int or not (0 <= code <= max_count):
            return _error("invalid_sentinels")
    sentinel_set = set(sentinels)

    # --- 7. frame_hex (hex text; spaces and underscores ignored) ---
    frame = payload.get("frame_hex", _MISSING)
    if type(frame) is not str:
        return _error("invalid_frame")
    cleaned = frame.replace(" ", "").replace("_", "")
    if not _HEX_RE.fullmatch(cleaned):
        return _error("invalid_frame")
    expected_hex_digits = width // 4
    if len(cleaned) != expected_hex_digits:
        return _error("frame_length")

    # --- 8. decode unsigned count from bytes ---
    raw_bytes = bytes.fromhex(cleaned)
    if byte_order == "little":
        raw_bytes = raw_bytes[::-1]
    unsigned_count = int.from_bytes(raw_bytes, "big")

    # --- 9. sentinel check on the unsigned bit pattern ---
    if unsigned_count in sentinel_set:
        return _error("sentinel")

    # --- 10. two's-complement signed interpretation ---
    if signed and unsigned_count >= (1 << (width - 1)):
        count = unsigned_count - (1 << width)
    else:
        count = unsigned_count

    # --- 11. scaled value, exact decimal arithmetic, ROUND_HALF_EVEN ---
    count_digits = len(str(abs(count)))
    scale_digits = len(scale_dec.as_tuple().digits)
    with localcontext() as ctx:
        ctx.prec = count_digits + scale_digits + places + 8
        product = Decimal(count) * scale_dec
        quantum = Decimal(1).scaleb(-places)
        result = product.quantize(quantum, rounding=ROUND_HALF_EVEN)
    if result == 0:
        result = result.abs()  # avoid negative-zero strings
    value_str = format(result, "f")

    return {"valid": True, "raw_count": count, "value": value_str}
