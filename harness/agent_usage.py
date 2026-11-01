"""Best-effort extraction of provider-reported token and cost usage events."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation


def _nonnegative_int(value):
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed >= 0 and str(parsed) == str(value) else None


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() and result >= 0 else None


def usage_from_event(event: dict) -> dict | None:
    """Extract recognizable usage fields; preserve source and never call cost confirmed."""
    candidates = []

    def visit(value):
        if isinstance(value, dict):
            if any(key in value for key in (
                "input_tokens", "prompt_tokens", "input", "output_tokens", "completion_tokens", "output", "total_tokens",
            )):
                candidates.append(value)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(event)
    for item in candidates:
        input_tokens = next((_nonnegative_int(item[key]) for key in ("input_tokens", "prompt_tokens", "input") if key in item and _nonnegative_int(item[key]) is not None), None)
        output_tokens = next((_nonnegative_int(item[key]) for key in ("output_tokens", "completion_tokens", "output") if key in item and _nonnegative_int(item[key]) is not None), None)
        total_tokens = _nonnegative_int(item.get("total_tokens"))
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens
        if total_tokens is None:
            continue
        raw_cost = item.get("cost_usd")
        if raw_cost is None and isinstance(event.get("type"), str) and event.get("type") in ("step_finish", "turn.completed"):
            raw_cost = item.get("cost")
        reported_cost = _number(raw_cost)
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "agent_reported_cost_usd": str(reported_cost) if reported_cost is not None else None,
            "source_event_type": event.get("type"),
            "billing_cost_confirmed": False,
        }
    return None

