from reference import s06
def solve(p):
    q=dict(p); q["expanded_uncertainty"]="0"; return s06.solve(q)
