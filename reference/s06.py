"""Known-correct conservative conformity rule."""
from decimal import localcontext
from .common import dec, fmt, invalid


def solve(payload: dict) -> dict:
    try:
        y, uncertainty = dec(payload["y"]), dec(payload["expanded_uncertainty"])
        low, high = dec(payload["lower_limit"]), dec(payload["upper_limit"])
        if uncertainty < 0:
            return invalid("negative_uncertainty")
        if low > high:
            return invalid("malformed_limits")
        with localcontext() as ctx:
            ctx.prec = 80
            lower, upper = y - uncertainty, y + uncertainty
            if lower >= low and upper <= high:
                decision = "ACCEPT"
            elif upper < low or lower > high:
                decision = "REJECT"
            else:
                decision = "INDETERMINATE"
            return {"valid": True, "lower": fmt(lower), "upper": fmt(upper), "decision": decision}
    except (KeyError, ValueError, TypeError):
        return invalid("invalid_parameters")
