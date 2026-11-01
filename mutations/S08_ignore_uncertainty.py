from reference import s08
def solve(p):
    r=s08.solve(p)
    if r.get("valid") and r.get("corrected_measurement"):
        y=r["corrected_measurement"]["value"]; lo=p["specification"]["lower_limit"]; hi=p["specification"]["upper_limit"]
        from decimal import Decimal
        y,lo,hi=map(Decimal,(y,lo,hi)); r["conformity_decision"]="ACCEPT" if lo<=y<=hi else "REJECT"
    return r
