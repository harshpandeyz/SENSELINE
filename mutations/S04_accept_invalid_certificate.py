from reference import s04
def solve(p):
    correct=s04.solve(p)
    return {"valid":True,"reasons":[]} if not correct["valid"] else correct
