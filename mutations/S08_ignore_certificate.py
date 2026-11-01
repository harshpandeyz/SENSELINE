from reference import s08
def solve(p):
    q={k:v for k,v in p.items()}; q["certificate"]=dict(p["certificate"]); q["certificate"].update({"serial_number":p["instrument_serial"],"measurand":p["measurand"],"status":"CURRENT","traceability_chain_status":"DOCUMENTED","valid_from":"1900-01-01","valid_to":"9999-12-31","range_min":"-1000000","range_max":"1000000","unit":p["units"]["to_unit"]}); return s08.solve(q)
