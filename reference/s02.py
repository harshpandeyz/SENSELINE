"""Known-correct exact affine unit conversions."""
from fractions import Fraction
from decimal import Decimal, localcontext
from .common import dec, rounded, invalid

UNITS = {
    "temperature": {"C": (Fraction(1), Fraction(0)), "F": (Fraction(5, 9), Fraction(-160, 9)), "K": (Fraction(1), Fraction(-27315, 100))},
    "pressure": {"Pa": (Fraction(1), Fraction(0)), "kPa": (Fraction(1000), Fraction(0)), "bar": (Fraction(100000), Fraction(0))},
    "voltage": {"V": (Fraction(1), Fraction(0)), "mV": (Fraction(1, 1000), Fraction(0))},
}


def solve(payload: dict) -> dict:
    try:
        source, target = payload["from_unit"], payload["to_unit"]
        pair = next((units for units in UNITS.values() if source in units and target in units), None)
        if pair is None:
            return invalid("incompatible_or_unknown_unit")
        a, b = pair[source]
        c, d = pair[target]
        with localcontext() as ctx:
            ctx.prec = 80
            base_value = dec(payload["value"]) * Decimal(a.numerator) / Decimal(a.denominator) + Decimal(b.numerator) / Decimal(b.denominator)
            converted = (base_value - Decimal(d.numerator) / Decimal(d.denominator)) * Decimal(c.denominator) / Decimal(c.numerator)
            return {"valid": True, "value": rounded(converted, payload["rounding_places"]), "unit": target}
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        return invalid("invalid_parameters")
