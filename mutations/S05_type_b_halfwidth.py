from decimal import Decimal, localcontext
from reference import s05
def solve(p):
    q={**p,"components":[dict(x) for x in p["components"]]}
    for x in q["components"]:
        if x.get("kind")=="type_b_rectangular": x["half_width"]=str(Decimal(str(x["half_width"]))/Decimal(3).sqrt())
    return s05.solve(q)
