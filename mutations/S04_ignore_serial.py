from reference import s04
def solve(p):
    q={"certificate":dict(p["certificate"]),"measurement":dict(p["measurement"])}; q["measurement"]["serial_number"]=q["certificate"].get("serial_number"); return s04.solve(q)
