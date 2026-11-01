from decimal import Decimal
from reference import s06
def solve(p):
    r=s06.solve(p)
    if r.get("valid") and r["decision"]=="ACCEPT":
        if Decimal(r["lower"])==Decimal(str(p["lower_limit"])) or Decimal(r["upper"])==Decimal(str(p["upper_limit"])): r["decision"]="INDETERMINATE"
    return r
