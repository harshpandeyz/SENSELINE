from reference import s02
def solve(p):
    r=s02.solve(p)
    if r.get("valid") and p.get("from_unit")!=p.get("to_unit"):
        return {"valid":True,"value":str(p["value"]),"unit":p["to_unit"]}
    return r
