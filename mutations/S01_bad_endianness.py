from reference import s01
def solve(p):
    q=dict(p); q["byte_order"]="big"; return s01.solve(q)
