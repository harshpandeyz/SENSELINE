from decimal import Decimal
from reference import s03
def solve(p):
    first=s03.solve(p)
    if not first.get("valid"): return first
    q=dict(p); q["raw_value"]=first["corrected_value"]; return s03.solve(q)
