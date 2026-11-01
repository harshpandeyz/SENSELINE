from reference import s07
def solve(p):
    r=s07.solve(p)
    if p.get("last_sequence") is not None and p.get("sequence",0)<p["last_sequence"] and r.get("valid"): return {"valid":False,"reason":"out_of_order_sequence"}
    return r
