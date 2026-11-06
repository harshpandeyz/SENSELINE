"""Decode a fixed-width sensor register frame into a signed/unsigned count
and a scaled physical value (see task.md for the full contract)."""

import re
from fractions import Fraction

_VALID_WIDTHS = (8, 16, 24, 32)
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_SCALE_RE = re.compile(r"[0-9]+(\.[0-9]+)?")


def _error(code: str) -> dict:
    return {"valid": False, "reason": code}


def _parse_scale(scale):
    """Return a Fraction for a strictly positive decimal scale, or None."""
    if type(scale) is str:
        if not _SCALE_RE.fullmatch(scale):
            return None
        if "." in scale:
            int_part, frac_part = scale.split(".")
            return Fraction(int(int_part + frac_part), 10 ** len(frac_part))
        return Fraction(int(scale))
    if type(scale) is int:  # bool is excluded (type(True) is not int)
        return Fraction(scale)
    return None


def solve(payload: dict) -> dict:
    # 1. width_bits
    width = payload.get("width_bits")
    if type(width) is not int or width not in _VALID_WIDTHS:
        return _error("invalid_width")

    # 2. byte_order
    byte_order = payload.get("byte_order")
    if byte_order not in ("big", "little"):
        return _error("invalid_byte_order")

    # 3. frame_hex: malformed text
    frame_hex = payload.get("frame_hex")
    if not isinstance(frame_hex, str):
        return _error("invalid_frame")
    cleaned = frame_hex.replace(" ", "").replace("_", "")
    if not cleaned or any(c not in _HEX_DIGITS for c in cleaned):
        return _error("invalid_frame")

    # 4. frame length (truncated / overlong)
    expected_hex_digits = width // 4
    if len(cleaned) != expected_hex_digits:
        return _error("frame_length")

    # 5. sentinel_codes validity
    sentinel_codes = payload.get("sentinel_codes", [])
    max_unsigned = (1 << width) - 1
    if not isinstance(sentinel_codes, list):
        return _error("invalid_sentinels")
    sentinel_set = set()
    for code in sentinel_codes:
        if type(code) is not int or not (0 <= code <= max_unsigned):
            return _error("invalid_sentinels")
        sentinel_set.add(code)

    # Apply byte order to the hex nibbles, then parse the unsigned pattern.
    if byte_order == "little":
        bytes_as_hex = [cleaned[i:i + 2] for i in range(0, len(cleaned), 2)]
        cleaned = "".join(reversed(bytes_as_hex))
    count_unsigned = int(cleaned, 16)

    # 6. sentinel match on the unsigned bit pattern (before signed decode).
    if count_unsigned in sentinel_set:
        return _error("sentinel")

    # 7. signed flag
    signed = payload.get("signed")
    if type(signed) is not bool:
        return _error("invalid_signed_flag")

    # 8. scale (strictly positive exact decimal)
    scale_fraction = _parse_scale(payload.get("scale"))
    if scale_fraction is None or scale_fraction <= 0:
        return _error("invalid_scale")

    # 9. rounding_places
    places = payload.get("rounding_places")
    if type(places) is not int or not (0 <= places <= 12):
        return _error("invalid_parameters")

    # Two's-complement signed interpretation.
    count = count_unsigned
    if signed and count >= (1 << (width - 1)):
        count -= 1 << width

    # value = count * scale, rounded with ROUND_HALF_EVEN (exact rational math).
    unit = Fraction(10 ** places)
    scaled = Fraction(count) * scale_fraction * unit
    floor = scaled.numerator // scaled.denominator
    remainder = scaled - floor
    half = Fraction(1, 2)
    if remainder > half:
        rounded = floor + 1
    elif remainder < half:
        rounded = floor
    else:  # exactly half: round to even
        rounded = floor if floor % 2 == 0 else floor + 1

    # Format as a decimal string with exactly `places` fractional digits.
    negative = rounded < 0
    magnitude = abs(rounded)
    int_part = magnitude // (10 ** places)
    frac_part = magnitude % (10 ** places)
    if int_part == 0 and frac_part == 0:
        negative = False  # normalize negative zero
    if places == 0:
        text = str(int_part)
    else:
        text = f"{int_part}.{frac_part:0{places}d}"
    if negative:
        text = "-" + text

    return {"valid": True, "raw_count": count, "value": text}
