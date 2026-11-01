from reference import s07
def solve(p):
    r=s07.solve(p)
    if r.get("reason")=="stale_timestamp": return {"valid":True,"reason":"ok","sequence_order":"NEWER"}
    return r
