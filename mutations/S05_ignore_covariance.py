from reference import s05
def solve(p):
    q=dict(p); q.pop("correlation_matrix",None); return s05.solve(q)
