"""Small input/format helpers used by the reference implementations only."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from typing import Any


def dec(value: Any) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("decimal values must be JSON strings or integers")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("invalid decimal") from None
    if not result.is_finite():
        raise ValueError("decimal must be finite")
    return result


def fmt(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def rounded(value: Decimal, places: int) -> str:
    if not isinstance(places, int) or isinstance(places, bool) or not 0 <= places <= 12:
        raise ValueError("rounding places must be an integer from 0 to 12")
    quantum = Decimal(1).scaleb(-places)
    return format(value.quantize(quantum, rounding=ROUND_HALF_EVEN), f".{places}f")


def invalid(reason: str) -> dict:
    return {"valid": False, "reason": reason}
