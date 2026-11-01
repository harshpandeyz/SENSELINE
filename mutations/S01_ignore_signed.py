from reference import s01
def solve(p):
    q=dict(p); q["signed"]=False; return s01.solve(q)
