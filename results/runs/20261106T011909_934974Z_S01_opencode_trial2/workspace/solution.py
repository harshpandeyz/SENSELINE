"""S01 — Raw Sensor Interpretation.

Decode one complete fixed-width register frame into a signed/unsigned count
and a scaled physical value. Implements solve(payload) -> dict.
"""

import re
from decimal import Decimal, ROUND_HALF_EVEN, localcontext

_VALID_WIDTHS = (8, 16, 24, 32)
_HEX_CHARS = set("0123456789abcdefABCDEF")
# Exact unsigned decimal: one or more digits, optional fractional part.
_SCALE_RE = re.compile(r"[0-9]+(\.[0-9]+)?")


def _error(code: str) -> dict:
    return {"valid": False, "reason": code}


def solve(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return _error("invalid_parameters")

    # --- Parameter validation -------------------------------------------
    width = payload.get("width_bits")
    if (
        isinstance(width, bool)
        or not isinstance(width, int)
        or width not in _VALID_WIDTHS
    ):
        return _error("invalid_width")

    byte_order = payload.get("byte_order")
    if byte_order not in ("big", "little"):
        return _error("invalid_byte_order")

    signed = payload.get("signed")
    if not isinstance(signed, bool):
        return _error("invalid_signed_flag")

    scale_raw = payload.get("scale")
    if isinstance(scale_raw, bool):
        return _error("invalid_scale")
    if isinstance(scale_raw, int):
        scale_text = str(scale_raw)
    elif isinstance(scale_raw, str):
        scale_text = scale_raw
    else:
        return _error("invalid_scale")
    if not _SCALE_RE.fullmatch(scale_text):
        return _error("invalid_scale")
    scale_dec = Decimal(scale_text)
    if scale_dec <= 0:
        return _error("invalid_scale")

    rounding_places = payload.get("rounding_places")
    if (
        isinstance(rounding_places, bool)
        or not isinstance(rounding_places, int)
        or not 0 <= rounding_places <= 12
    ):
        return _error("invalid_parameters")

    # --- Sentinel codes -------------------------------------------------
    sentinel_raw = payload.get("sentinel_codes", [])
    if not isinstance(sentinel_raw, list):
        return _error("invalid_sentinels")
    limit = 1 << width
    sentinels = set()
    for code in sentinel_raw:
        if (
            isinstance(code, bool)
            or not isinstance(code, int)
            or code < 0
            or code >= limit
        ):
            return _error("invalid_sentinels")
        sentinels.add(code)

    # --- Frame decoding -------------------------------------------------
    frame_hex = payload.get("frame_hex")
    if not isinstance(frame_hex, str):
        return _error("invalid_frame")
    cleaned = frame_hex.replace(" ", "").replace("_", "")
    if not cleaned or any(c not in _HEX_CHARS for c in cleaned):
        return _error("invalid_frame")

    expected_hex_len = width // 4
    if len(cleaned) != expected_hex_len:
        return _error("frame_length")

    unsigned = int.from_bytes(bytes.fromhex(cleaned), byte_order)

    # Sentinel codes are unsigned bit patterns, checked before signed decode.
    if unsigned in sentinels:
        return _error("sentinel")

    if signed and unsigned >= (1 << (width - 1)):
        count = unsigned - (1 << width)
    else:
        count = unsigned

    # --- Scaled physical value ------------------------------------------
    scale_digits = len(scale_text.replace(".", "").lstrip("0")) or 1
    prec = max(80, len(str(abs(count))) + scale_digits + rounding_places + 10)
    with localcontext() as ctx:
        ctx.prec = prec
        value = (Decimal(count) * scale_dec).quantize(
            Decimal(1).scaleb(-rounding_places),
            rounding=ROUND_HALF_EVEN,
        )

    return {"valid": True, "raw_count": count, "value": format(value, "f")}
