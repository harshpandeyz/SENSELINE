"""Create the original per-task and targeted intentionally defective candidate controls."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FILES={
"S01_ignore_signed.py":'''from reference import s01\ndef solve(p):\n    q=dict(p); q["signed"]=False; return s01.solve(q)\n''',
"S01_ignore_sentinels.py":'''from reference import s01\ndef solve(p):\n    q=dict(p); q["sentinel_codes"]=[]; return s01.solve(q)\n''',
"S02_bad_fahrenheit.py":'''from decimal import Decimal, ROUND_HALF_EVEN\nfrom reference import s02\ndef solve(p):\n    if p.get("from_unit")=="F" and p.get("to_unit")=="C":\n        x=Decimal(str(p["value"]))*Decimal(5)/Decimal(9)+Decimal(32)\n        return {"valid":True,"value":format(x.quantize(Decimal(1).scaleb(-p["rounding_places"]),rounding=ROUND_HALF_EVEN),f".{p['rounding_places']}f"),"unit":"C"}\n    return s02.solve(p)\n''',
"S02_allow_incompatible.py":'''from reference import s02\ndef solve(p):\n    result=s02.solve(p)\n    if not result["valid"] and result.get("reason")=="incompatible_or_unknown_unit": return {"valid":True,"value":str(p["value"]),"unit":p["to_unit"]}\n    return result\n''',
"S03_omit_temperature.py":'''from reference import s03\ndef solve(p):\n    q=dict(p); q["temp_coefficient"]="0"; return s03.solve(q)\n''',
"S03_gain_offset_order.py":'''from decimal import Decimal, ROUND_HALF_EVEN\nfrom reference import s03\ndef solve(p):\n    if p.get("correction_state")!="RAW": return s03.solve(p)\n    try:\n        v=Decimal(str(p["gain"]))*(Decimal(str(p["raw_value"]))+Decimal(str(p["offset"])))+Decimal(str(p["temp_coefficient"]))*(Decimal(str(p["ambient_temperature_c"]))-Decimal(str(p["reference_temperature_c"])))\n        n=p["rounding_places"]; return {"valid":True,"corrected_value":format(v.quantize(Decimal(1).scaleb(-n),rounding=ROUND_HALF_EVEN),f".{n}f")}\n    except Exception: return s03.solve(p)\n''',
"S04_ignore_serial.py":'''from reference import s04\ndef solve(p):\n    q={"certificate":dict(p["certificate"]),"measurement":dict(p["measurement"])}; q["measurement"]["serial_number"]=q["certificate"].get("serial_number"); return s04.solve(q)\n''',
"S04_ignore_traceability.py":'''from reference import s04\ndef solve(p):\n    q={"certificate":dict(p["certificate"]),"measurement":dict(p["measurement"])}; q["certificate"]["traceability_chain_status"]="DOCUMENTED"; return s04.solve(q)\n''',
"S05_drop_correlation.py":'''from reference import s05\ndef solve(p):\n    q=dict(p); q.pop("correlation_matrix",None); return s05.solve(q)\n''',
"S05_type_b_halfwidth.py":'''from decimal import Decimal, localcontext\nfrom reference import s05\ndef solve(p):\n    q={**p,"components":[dict(x) for x in p["components"]]}\n    for x in q["components"]:\n        if x.get("kind")=="type_b_rectangular": x["half_width"]=str(Decimal(str(x["half_width"]))/Decimal(3).sqrt())\n    return s05.solve(q)\n''',
"S06_point_only.py":'''from reference import s06\ndef solve(p):\n    q=dict(p); q["expanded_uncertainty"]="0"; return s06.solve(q)\n''',
"S06_touching_is_reject.py":'''from decimal import Decimal\nfrom reference import s06\ndef solve(p):\n    r=s06.solve(p)\n    if r.get("valid") and r["decision"]=="INDETERMINATE":\n        if Decimal(r["upper"])==Decimal(str(p["lower_limit"])) or Decimal(r["lower"])==Decimal(str(p["upper_limit"])): r["decision"]="REJECT"\n    return r\n''',
"S07_no_rollover.py":'''from reference import s07\ndef solve(p):\n    r=s07.solve(p)\n    if p.get("last_sequence") is not None and p.get("sequence",0)<p["last_sequence"] and r.get("valid"):\n        return {"valid":False,"reason":"out_of_order_sequence"}\n    return r\n''',
"S07_ignore_freshness.py":'''from reference import s07\ndef solve(p):\n    q=dict(p); q["max_age_ms"]=10**18; q["allowed_future_skew_ms"]=10**18; return s07.solve(q)\n''',
"S08_ignore_certificate.py":'''from reference import s08\ndef solve(p):\n    q={k:v for k,v in p.items()}; q["certificate"]=dict(p["certificate"]); q["certificate"].update({"serial_number":p["instrument_serial"],"measurand":p["measurand"],"status":"CURRENT","traceability_chain_status":"DOCUMENTED","valid_from":"1900-01-01","valid_to":"9999-12-31","range_min":"-1000000","range_max":"1000000","unit":p["units"]["to_unit"]}); return s08.solve(q)\n''',
"S08_ignore_uncertainty.py":'''from reference import s08\ndef solve(p):\n    r=s08.solve(p)\n    if r.get("valid") and r.get("corrected_measurement"):\n        y=r["corrected_measurement"]["value"]; lo=p["specification"]["lower_limit"]; hi=p["specification"]["upper_limit"]\n        from decimal import Decimal\n        y,lo,hi=map(Decimal,(y,lo,hi)); r["conformity_decision"]="ACCEPT" if lo<=y<=hi else "REJECT"\n    return r\n''',
"S01_bad_signed_decode.py":'''from reference import s01\ndef solve(p):\n    q=dict(p); q["signed"]=False; return s01.solve(q)\n''',
"S01_bad_endianness.py":'''from reference import s01\ndef solve(p):\n    q=dict(p); q["byte_order"]="big"; return s01.solve(q)\n''',
"S02_wrong_unit_conversion.py":'''from reference import s02\ndef solve(p):\n    r=s02.solve(p)\n    if r.get("valid") and p.get("from_unit")!=p.get("to_unit"):\n        return {"valid":True,"value":str(p["value"]),"unit":p["to_unit"]}\n    return r\n''',
"S03_missing_compensation.py":'''from reference import s03\ndef solve(p):\n    q=dict(p); q["temp_coefficient"]="0"; return s03.solve(q)\n''',
"S03_double_calibration.py":'''from decimal import Decimal\nfrom reference import s03\ndef solve(p):\n    first=s03.solve(p)\n    if not first.get("valid"): return first\n    q=dict(p); q["raw_value"]=first["corrected_value"]; return s03.solve(q)\n''',
"S04_accept_invalid_certificate.py":'''from reference import s04\ndef solve(p):\n    correct=s04.solve(p)\n    return {"valid":True,"reasons":[]} if not correct["valid"] else correct\n''',
"S05_drop_uncertainty_component.py":'''from reference import s05\ndef solve(p):\n    if len(p.get("components",[]))<2: return s05.solve(p)\n    q=dict(p); q["components"]=p["components"][:-1]; q.pop("correlation_matrix",None); return s05.solve(q)\n''',
"S05_ignore_covariance.py":'''from reference import s05\ndef solve(p):\n    q=dict(p); q.pop("correlation_matrix",None); return s05.solve(q)\n''',
"S06_wrong_equality_boundary.py":'''from decimal import Decimal\nfrom reference import s06\ndef solve(p):\n    r=s06.solve(p)\n    if r.get("valid") and r["decision"]=="ACCEPT":\n        if Decimal(r["lower"])==Decimal(str(p["lower_limit"])) or Decimal(r["upper"])==Decimal(str(p["upper_limit"])): r["decision"]="INDETERMINATE"\n    return r\n''',
"S07_accept_stale.py":'''from reference import s07\ndef solve(p):\n    r=s07.solve(p)\n    if r.get("reason")=="stale_timestamp": return {"valid":True,"reason":"ok","sequence_order":"NEWER"}\n    return r\n''',
"S07_bad_rollover.py":'''from reference import s07\ndef solve(p):\n    r=s07.solve(p)\n    if p.get("last_sequence") is not None and p.get("sequence",0)<p["last_sequence"] and r.get("valid"): return {"valid":False,"reason":"out_of_order_sequence"}\n    return r\n''',
"S08_wrong_unit_transformation.py":'''from reference import s08\ndef solve(p):\n    q={**p,"units":dict(p["units"])}\n    if q["units"].get("from_unit")=="F" and q["units"].get("to_unit")=="C": q["units"]["from_unit"]="C"\n    return s08.solve(q)\n''',
"S08_extra_schema_field.py":'''from reference import s08\ndef solve(p):\n    result=s08.solve(p); result["debug"]="diagnostic-only"; return result\n'''
}

def main():
    target=ROOT/"mutations"
    for name,source in FILES.items(): (target/name).write_text(source,encoding="utf-8")
    print(f"wrote {len(FILES)} defective controls")

if __name__=="__main__": main()
