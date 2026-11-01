"""Known-correct calibration and ambient-temperature compensation."""
from decimal import localcontext
from .common import dec, rounded, invalid


def solve(payload: dict) -> dict:
    try:
        if payload["correction_state"] != "RAW":
            return invalid("already_corrected")
        raw, gain, offset = dec(payload["raw_value"]), dec(payload["gain"]), dec(payload["offset"])
        if gain <= 0:
            return invalid("invalid_gain")
        tc, ambient, reference = dec(payload["temp_coefficient"]), dec(payload["ambient_temperature_c"]), dec(payload["reference_temperature_c"])
        with localcontext() as ctx:
            ctx.prec = 80
            value = gain * raw + offset + tc * (ambient - reference)
            return {"valid": True, "corrected_value": rounded(value, payload["rounding_places"])}
    except (KeyError, ValueError, TypeError):
        return invalid("invalid_parameters")
