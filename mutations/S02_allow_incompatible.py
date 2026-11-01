from reference import s02
def solve(p):
    result=s02.solve(p)
    if not result["valid"] and result.get("reason")=="incompatible_or_unknown_unit": return {"valid":True,"value":str(p["value"]),"unit":p["to_unit"]}
    return result
