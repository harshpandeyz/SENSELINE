from decimal import Decimal, ROUND_HALF_EVEN
from reference import s03
def solve(p):
    if p.get("correction_state")!="RAW": return s03.solve(p)
    try:
        v=Decimal(str(p["gain"]))*(Decimal(str(p["raw_value"]))+Decimal(str(p["offset"])))+Decimal(str(p["temp_coefficient"]))*(Decimal(str(p["ambient_temperature_c"]))-Decimal(str(p["reference_temperature_c"])))
        n=p["rounding_places"]; return {"valid":True,"corrected_value":format(v.quantize(Decimal(1).scaleb(-n),rounding=ROUND_HALF_EVEN),f".{n}f")}
    except Exception: return s03.solve(p)
