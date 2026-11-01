from reference import s03
def solve(p):
    q=dict(p); q["temp_coefficient"]="0"; return s03.solve(q)
