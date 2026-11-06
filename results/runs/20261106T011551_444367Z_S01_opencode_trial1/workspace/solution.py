"""S01 — Raw Sensor Interpretation.

Decodes one fixed-width register frame into a signed or unsigned count and a
scaled physical value. See task.md for the full specification.
"""

import re
from decimal import Decimal, ROUND_HALF_EVEN, localcontext

_VALID_WIDTHS = (8, 16, 24, 32)
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
_SCALE_RE = re.compile(r"^[0-9]+(\.[0-9]+)?$")


def _error(code):
    return {"valid": False, "reason": code}


def solve(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return _error("invalid_parameters")

    # --- 1. width_bits ---------------------------------------------------
    if "width_bits" not in payload:
        return _error("invalid_width")
    width_bits = payload["width_bits"]
    if (
        isinstance(width_bits, bool)
        or not isinstance(width_bits, int)
        or width_bits not in _VALID_WIDTHS
    ):
        return _error("invalid_width")

    # --- 2. byte_order ---------------------------------------------------
    if "byte_order" not in payload:
        return _error("invalid_byte_order")
    byte_order = payload["byte_order"]
    if byte_order not in ("big", "little"):
        return _error("invalid_byte_order")

    # --- 3. frame_hex format ---------------------------------------------
    if "frame_hex" not in payload:
        return _error("invalid_frame")
    frame_hex = payload["frame_hex"]
    if not isinstance(frame_hex, str):
        return _error("invalid_frame")
    cleaned = frame_hex.replace(" ", "").replace("_", "")
    if not cleaned or not _HEX_RE.match(cleaned) or len(cleaned) % 2 != 0:
        return _error("invalid_frame")

    # --- 4. frame length -------------------------------------------------
    expected_bytes = width_bits // 8
    if len(cleaned) // 2 != expected_bytes:
        return _error("frame_length")

    # --- 5. sentinel_codes validity --------------------------------------
    sentinel_codes = payload.get("sentinel_codes", [])
    if not isinstance(sentinel_codes, list):
        return _error("invalid_sentinels")
    max_uint = (1 << width_bits) - 1
    for code in sentinel_codes:
        if (
            isinstance(code, bool)
            or not isinstance(code, int)
            or code < 0
            or code > max_uint
        ):
            return _error("invalid_sentinels")

    # --- 6. parse frame; sentinel checked before signed interpretation ---
    raw_bytes = int(cleaned, 16).to_bytes(expected_bytes, "big")
    if byte_order == "little":
        raw_bytes = raw_bytes[::-1]
    unsigned_count = int.from_bytes(raw_bytes, "big")
    if unsigned_count in sentinel_codes:
        return _error("sentinel")

    # --- 7. signed flag --------------------------------------------------
    if "signed" not in payload:
        return _error("invalid_signed_flag")
    signed = payload["signed"]
    if not isinstance(signed, bool):
        return _error("invalid_signed_flag")

    # --- 8. scale --------------------------------------------------------
    if "scale" not in payload:
        return _error("invalid_scale")
    scale = payload["scale"]
    if isinstance(scale, bool):
        return _error("invalid_scale")
    if isinstance(scale, int):
        if scale <= 0:
            return _error("invalid_scale")
        scale_dec = Decimal(scale)
    elif isinstance(scale, str):
        if not _SCALE_RE.match(scale):
            return _error("invalid_scale")
        scale_dec = Decimal(scale)
        if scale_dec <= 0:
            return _error("invalid_scale")
    else:
        return _error("invalid_scale")

    # --- 9. rounding_places ----------------------------------------------
    if "rounding_places" not in payload:
        return _error("invalid_parameters")
    rounding_places = payload["rounding_places"]
    if (
        isinstance(rounding_places, bool)
        or not isinstance(rounding_places, int)
        or rounding_places < 0
        or rounding_places > 12
    ):
        return _error("invalid_parameters")

    # --- decode count (two's complement when signed) ---------------------
    if signed and unsigned_count >= (1 << (width_bits - 1)):
        raw_count = unsigned_count - (1 << width_bits)
    else:
        raw_count = unsigned_count

    # --- scaled value: exact decimal multiplication, ROUND_HALF_EVEN -----
    count_digits = 1 if raw_count == 0 else len(str(abs(raw_count)))
    scale_digits = len(scale_dec.as_tuple().digits)
    with localcontext() as ctx:
        ctx.prec = max(100, count_digits + scale_digits + rounding_places + 10)
        product = Decimal(raw_count) * scale_dec
        quantum = Decimal(1).scaleb(-rounding_places)
        rounded = product.quantize(quantum, rounding=ROUND_HALF_EVEN)
        if rounded == 0:
            rounded = abs(rounded)  # normalize negative zero, keep scale
    value = format(rounded, "f")

    return {"valid": True, "raw_count": raw_count, "value": value}
