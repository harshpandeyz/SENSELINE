from decimal import Decimal, ROUND_HALF_EVEN
from reference import s02
def solve(p):
    if p.get("from_unit")=="F" and p.get("to_unit")=="C":
        x=Decimal(str(p["value"]))*Decimal(5)/Decimal(9)+Decimal(32)
        return {"valid":True,"value":format(x.quantize(Decimal(1).scaleb(-p["rounding_places"]),rounding=ROUND_HALF_EVEN),f".{p['rounding_places']}f"),"unit":"C"}
    return s02.solve(p)
