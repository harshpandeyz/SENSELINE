"""Known-correct S01 raw register decoder."""
from decimal import localcontext
from .common import dec, rounded, invalid


def solve(payload: dict) -> dict:
    try:
        width = payload["width_bits"]
        if not isinstance(width, int) or isinstance(width, bool) or width not in (8, 16, 24, 32):
            return invalid("invalid_width")
        if payload["byte_order"] not in ("big", "little"):
            return invalid("invalid_byte_order")
        raw_hex = payload["frame_hex"]
        if not isinstance(raw_hex, str):
            return invalid("invalid_frame")
        compact = raw_hex.replace(" ", "").replace("_", "")
        if any(char not in "0123456789abcdefABCDEF" for char in compact):
            return invalid("invalid_frame")
        try:
            frame = bytes.fromhex(compact)
        except ValueError:
            return invalid("invalid_frame")
        if len(frame) != width // 8:
            return invalid("frame_length")
        unsigned = int.from_bytes(frame, payload["byte_order"], signed=False)
        sentinels = payload.get("sentinel_codes", [])
        if not isinstance(sentinels, list) or any(not isinstance(x, int) or isinstance(x, bool) for x in sentinels):
            return invalid("invalid_sentinels")
        if any(x < 0 or x >= (1 << width) for x in sentinels):
            return invalid("invalid_sentinels")
        if unsigned in sentinels:
            return invalid("sentinel")
        signed = payload["signed"]
        if not isinstance(signed, bool):
            return invalid("invalid_signed_flag")
        count = unsigned
        if signed and unsigned & (1 << (width - 1)):
            count = unsigned - (1 << width)
        scale = dec(payload["scale"])
        if scale <= 0:
            return invalid("invalid_scale")
        with localcontext() as ctx:
            ctx.prec = 80
            value = dec(count) * scale
            return {"valid": True, "raw_count": count, "value": rounded(value, payload["rounding_places"])}
    except (KeyError, ValueError, TypeError):
        return invalid("invalid_parameters")
