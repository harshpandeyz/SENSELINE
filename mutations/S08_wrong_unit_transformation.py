from reference import s08
def solve(p):
    q={**p,"units":dict(p["units"])}
    if q["units"].get("from_unit")=="F" and q["units"].get("to_unit")=="C": q["units"]["from_unit"]="C"
    return s08.solve(q)
