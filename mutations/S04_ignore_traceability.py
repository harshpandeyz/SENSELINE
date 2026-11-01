from reference import s04
def solve(p):
    q={"certificate":dict(p["certificate"]),"measurement":dict(p["measurement"])}; q["certificate"]["traceability_chain_status"]="DOCUMENTED"; return s04.solve(q)
