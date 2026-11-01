"""Known-correct UTC timestamp and uint32 modular sequence checks."""
MODULUS = 1 << 32
HALF = 1 << 31


def solve(payload: dict) -> dict:
    try:
        ts, now = payload["timestamp_ms"], payload["now_ms"]
        age, skew, seq = payload["max_age_ms"], payload["allowed_future_skew_ms"], payload["sequence"]
        ints = (ts, now, age, skew, seq)
        if any(not isinstance(v, int) or isinstance(v, bool) for v in ints) or age < 0 or skew < 0 or not 0 <= seq < MODULUS:
            return {"valid": False, "reason": "invalid_timestamp_or_parameters"}
        if ts < 0 or now < 0:
            return {"valid": False, "reason": "invalid_timestamp_or_parameters"}
        if ts > now + skew:
            return {"valid": False, "reason": "future_timestamp"}
        if ts < now - age:
            return {"valid": False, "reason": "stale_timestamp"}
        if "last_sequence" not in payload or payload["last_sequence"] is None:
            return {"valid": True, "reason": "first_sequence", "sequence_order": "FIRST"}
        last = payload["last_sequence"]
        if not isinstance(last, int) or isinstance(last, bool) or not 0 <= last < MODULUS:
            return {"valid": False, "reason": "invalid_last_sequence"}
        delta = (seq - last) % MODULUS
        if delta == 0:
            return {"valid": False, "reason": "duplicate_sequence"}
        if delta == HALF:
            return {"valid": False, "reason": "ambiguous_half_range"}
        if delta > HALF:
            return {"valid": False, "reason": "out_of_order_sequence"}
        return {"valid": True, "reason": "ok", "sequence_order": "NEWER"}
    except (KeyError, TypeError):
        return {"valid": False, "reason": "invalid_structure"}
