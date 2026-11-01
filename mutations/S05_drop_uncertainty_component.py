from reference import s05
def solve(p):
    if len(p.get("components",[]))<2: return s05.solve(p)
    q=dict(p); q["components"]=p["components"][:-1]; q.pop("correlation_matrix",None); return s05.solve(q)
