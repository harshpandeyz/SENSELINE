from reference import s07
def solve(p):
    q=dict(p); q["max_age_ms"]=10**18; q["allowed_future_skew_ms"]=10**18; return s07.solve(q)
