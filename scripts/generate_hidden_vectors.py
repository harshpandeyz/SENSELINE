"""Generate deterministic, agent-hidden cases and oracle-produced golden outputs."""
import copy
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from oracle.compute import SOLVERS
from simulator.synthetic import encode_register_count

MASTER_SEED = 20261101


def case(code, name, payload, category="ordinary"):
    return {"id": f"{code}-{name}", "category": category, "input": payload}


def make_s01(rng):
    out=[]
    for i in range(18):
        bits=(8,16,24,32)[i%4]
        signed=i%2==0
        lo=-(1<<(bits-1)) if signed else 0
        hi=(1<<(bits-(1 if signed else 0)))-1
        n=rng.randint(lo,hi)
        order="big" if i%2==0 else "little"
        frame=encode_register_count(n,bits,order,signed)
        out.append(case("S01",f"seeded-{i:02}",{"frame_hex":frame,"width_bits":bits,"byte_order":order,"signed":signed,"scale":str(rng.choice(["0.001","0.01","0.5","2"])),"rounding_places":3,"sentinel_codes":[]}))
    out += [
        case("S01","signed-min",{"frame_hex":"80","width_bits":8,"byte_order":"big","signed":True,"scale":"1","rounding_places":0,"sentinel_codes":[]},"boundary"),
        case("S01","signed-max",{"frame_hex":"7F","width_bits":8,"byte_order":"big","signed":True,"scale":"1","rounding_places":0,"sentinel_codes":[]},"boundary"),
        case("S01","unsigned-max",{"frame_hex":"FFFF","width_bits":16,"byte_order":"big","signed":False,"scale":"1","rounding_places":0,"sentinel_codes":[]},"boundary"),
        case("S01","little-endian",{"frame_hex":"3412","width_bits":16,"byte_order":"little","signed":False,"scale":"0.1","rounding_places":1,"sentinel_codes":[]},"boundary"),
        case("S01","sentinel",{"frame_hex":"FF","width_bits":8,"byte_order":"big","signed":True,"scale":"1","rounding_places":0,"sentinel_codes":[255]},"adversarial"),
        case("S01","truncated",{"frame_hex":"12","width_bits":16,"byte_order":"big","signed":False,"scale":"1","rounding_places":0,"sentinel_codes":[]},"adversarial"),
        case("S01","malformed-hex",{"frame_hex":"GG","width_bits":8,"byte_order":"big","signed":False,"scale":"1","rounding_places":0,"sentinel_codes":[]},"adversarial"),
        case("S01","bad-scale",{"frame_hex":"01","width_bits":8,"byte_order":"big","signed":False,"scale":"NaN","rounding_places":0,"sentinel_codes":[]},"adversarial"),
        case("S01","bad-width",{"frame_hex":"0000","width_bits":12,"byte_order":"big","signed":False,"scale":"1","rounding_places":0,"sentinel_codes":[]},"adversarial"),
        case("S01","round-half-even",{"frame_hex":"03","width_bits":8,"byte_order":"big","signed":False,"scale":"0.5","rounding_places":0,"sentinel_codes":[]},"boundary"),
        case("S01","odd-nibble",{"frame_hex":"F","width_bits":8,"byte_order":"big","signed":False,"scale":"1","rounding_places":0,"sentinel_codes":[]},"adversarial"),
        case("S01","negative-scale",{"frame_hex":"01","width_bits":8,"byte_order":"big","signed":False,"scale":"-1","rounding_places":0,"sentinel_codes":[]},"adversarial"),
        case("S01","sentinel-out-of-width",{"frame_hex":"01","width_bits":8,"byte_order":"big","signed":False,"scale":"1","rounding_places":0,"sentinel_codes":[256]},"adversarial"),
        case("S01","tab-separator-not-allowed",{"frame_hex":"00\t01","width_bits":16,"byte_order":"big","signed":False,"scale":"1","rounding_places":0,"sentinel_codes":[]},"adversarial"),
    ]
    return out


def make_s02(rng):
    pairs=[("C","F"),("F","C"),("C","K"),("K","C"),("Pa","kPa"),("kPa","Pa"),("bar","Pa"),("Pa","bar"),("V","mV"),("mV","V")]
    out=[]
    for i in range(20):
        a,b=pairs[i%len(pairs)]
        val=rng.choice(["0","1","-40","32","273.15","101325","1.25","-0.005","1000000"])
        out.append(case("S02",f"seeded-{i:02}",{"value":val,"from_unit":a,"to_unit":b,"rounding_places":5}))
    out += [
        case("S02","same-unit",{"value":"-273.15","from_unit":"C","to_unit":"C","rounding_places":2},"boundary"),
        case("S02","incompatible",{"value":"1","from_unit":"V","to_unit":"Pa","rounding_places":2},"adversarial"),
        case("S02","unknown-unit",{"value":"1","from_unit":"psi","to_unit":"Pa","rounding_places":2},"adversarial"),
        case("S02","half-even-down",{"value":"1.245","from_unit":"V","to_unit":"V","rounding_places":2},"boundary"),
        case("S02","half-even-up",{"value":"1.255","from_unit":"V","to_unit":"V","rounding_places":2},"boundary"),
        case("S02","bad-decimal",{"value":"Infinity","from_unit":"C","to_unit":"K","rounding_places":2},"adversarial"),
        case("S02","bad-precision",{"value":"3","from_unit":"Pa","to_unit":"kPa","rounding_places":99},"adversarial"),
        case("S02","absolute-zero",{"value":"0","from_unit":"K","to_unit":"C","rounding_places":2},"boundary"),
        case("S02","negative-pressure",{"value":"-2","from_unit":"bar","to_unit":"kPa","rounding_places":3},"boundary"),
        case("S02","milli",{"value":"2500","from_unit":"mV","to_unit":"V","rounding_places":3},"boundary"),
    ]
    return out


def make_s03(rng):
    out=[]
    for i in range(20):
        out.append(case("S03",f"seeded-{i:02}",{"raw_value":str(rng.randint(-100,100)),"gain":str(rng.choice(["0.5","1","1.02","2.5"])),"offset":str(rng.randint(-5,5)),"temp_coefficient":rng.choice(["0","0.01","-0.02"]),"ambient_temperature_c":str(rng.randint(-20,60)),"reference_temperature_c":"20","correction_state":"RAW","rounding_places":4}))
    base={"raw_value":"10","gain":"1","offset":"0","temp_coefficient":"0","ambient_temperature_c":"20","reference_temperature_c":"20","correction_state":"RAW","rounding_places":2}
    out += [
        case("S03","zero-temp-delta",base,"boundary"),
        case("S03","temp-compensation",{**base,"temp_coefficient":"0.2","ambient_temperature_c":"25"},"boundary"),
        case("S03","negative-gain",{**base,"gain":"-1"},"adversarial"),
        case("S03","zero-gain",{**base,"gain":"0"},"adversarial"),
        case("S03","double-correction",{**base,"correction_state":"CORRECTED"},"adversarial"),
        case("S03","missing-coefficient",{k:v for k,v in base.items() if k!="temp_coefficient"},"adversarial"),
        case("S03","nonfinite",{**base,"offset":"NaN"},"adversarial"),
        case("S03","round-half-even",{**base,"raw_value":"1.245","rounding_places":2},"boundary"),
        case("S03","negative-temps",{**base,"ambient_temperature_c":"-40","reference_temperature_c":"0","temp_coefficient":"0.1"},"boundary"),
        case("S03","large-offset",{**base,"offset":"1000000000"},"boundary"),
    ]
    return out


def cert_base():
    return {"serial_number":"SN-17","measurand":"temperature","status":"CURRENT","valid_from":"2026-01-01","valid_to":"2026-12-31","range_min":"-20","range_max":"100","uncertainty":"0.2","unit":"C","traceability_chain_status":"DOCUMENTED"}


def meas_base(): return {"serial_number":"SN-17","measurand":"temperature","date":"2026-11-01","value":"25","unit":"C"}


def make_s04(rng):
    out=[]
    for i in range(18):
        c=cert_base(); m=meas_base()
        if i%3==0: m["value"]=str(rng.randint(-20,100))
        elif i%3==1: m["date"]=f"2026-{rng.randint(1,12):02}-15"
        else: c["uncertainty"]=str(rng.choice(["0","0.01","1.5"]))
        out.append(case("S04",f"seeded-{i:02}",{"certificate":c,"measurement":m}))
    mods=[
        ("valid-start",{}, {"date":"2026-01-01"},"boundary"),
        ("valid-end",{}, {"date":"2026-12-31"},"boundary"),
        ("outside-start",{}, {"date":"2025-12-31"},"adversarial"),
        ("serial-mismatch",{"serial_number":"SN-X"},{},"adversarial"),
        ("measurand-mismatch",{"measurand":"pressure"},{},"adversarial"),
        ("expired-status",{"status":"EXPIRED"},{},"adversarial"),
        ("range-low",{}, {"value":"-20"},"boundary"),
        ("range-high",{}, {"value":"100"},"boundary"),
        ("outside-range",{}, {"value":"100.01"},"adversarial"),
        ("negative-u",{"uncertainty":"-0.1"},{},"adversarial"),
        ("unit-mismatch",{"unit":"K"},{},"adversarial"),
        ("traceability-unknown",{"traceability_chain_status":"UNKNOWN"},{},"adversarial"),
        ("malformed-date",{}, {"date":"2026-02-30"},"adversarial"),
        ("week-date",{}, {"date":"2026-W44-7"},"adversarial"),
        ("reversed-range",{"range_min":"10","range_max":"0"},{},"adversarial"),
    ]
    for name,cm,mm,cat in mods:
        c=cert_base(); m=meas_base(); c.update(cm); m.update(mm)
        out.append(case("S04",name,{"certificate":c,"measurement":m},cat))
    # Missing-field combinations exercise independent checks without testing comparisons
    # that require a missing certificate value.
    c=cert_base(); m=meas_base(); del c["valid_from"]
    out.append(case("S04","missing-valid-from-plus-measurand",{"certificate":c,"measurement":{**m,"measurand":"pressure"}},"adversarial"))
    c=cert_base(); m=meas_base(); del c["range_max"]
    out.append(case("S04","missing-range-max-plus-bad-value",{"certificate":c,"measurement":{**m,"value":"not-a-reading"}},"adversarial"))
    c=cert_base(); m=meas_base(); del c["serial_number"]; del c["unit"]
    out.append(case("S04","missing-serial-and-unit",{"certificate":c,"measurement":m},"adversarial"))
    c=cert_base(); m=meas_base()
    del c["serial_number"]
    c.update({"measurand":"pressure","status":"EXPIRED","valid_to":"2026-10-31","uncertainty":"-0.2","unit":"K","traceability_chain_status":"UNKNOWN"})
    out.append(case("S04","simultaneous-independent-defects",{"certificate":c,"measurement":m},"adversarial"))
    return out


def make_s05(rng):
    out=[]
    for i in range(18):
        vals=sorted(rng.sample(range(-10,11),4))
        p={"components":[{"kind":"type_a","observations":[str(x) for x in vals],"sensitivity":str(rng.choice([-2,-1,1,2]))},{"kind":"type_b_rectangular","half_width":str(rng.choice(["0.1","0.5","1.5"])),"sensitivity":str(rng.choice(["0.5","1","2"]))}],"coverage_factor":str(rng.choice(["1","2","2.5"]))}
        if i%2==0: p["correlation_matrix"]=[["1",str(rng.choice(["-0.5","0","0.5"]))],[str(rng.choice(["-0.5","0","0.5"])),"1"]]
        # Make the 2x2 matrix symmetric by using a single draw if supplied.
        if i%2==0:
            rho=str(rng.choice(["-0.5","0","0.5"]))
            p["correlation_matrix"]=[["1",rho],[rho,"1"]]
        out.append(case("S05",f"seeded-{i:02}",p))
    out += [
        case("S05","type-a-known",{"components":[{"kind":"type_a","observations":["1","2","3"],"sensitivity":"1"}],"coverage_factor":"2"},"boundary"),
        case("S05","type-b-known",{"components":[{"kind":"type_b_rectangular","half_width":"1.732050807568877293527446341505872366943","sensitivity":"1"}],"coverage_factor":"2"},"boundary"),
        case("S05","correlation-positive",{"components":[{"kind":"type_b_rectangular","half_width":"1.732050807568877293527446341505872366943","sensitivity":"1"},{"kind":"type_b_rectangular","half_width":"1.732050807568877293527446341505872366943","sensitivity":"1"}],"coverage_factor":"2","correlation_matrix":[["1","0.5"],["0.5","1"]]},"boundary"),
        case("S05","correlation-negative",{"components":[{"kind":"type_b_rectangular","half_width":"1.732050807568877293527446341505872366943","sensitivity":"1"},{"kind":"type_b_rectangular","half_width":"1.732050807568877293527446341505872366943","sensitivity":"1"}],"coverage_factor":"2","correlation_matrix":[["1","-0.5"],["-0.5","1"]]},"boundary"),
        case("S05","non-psd",{"components":[{"kind":"type_b_rectangular","half_width":"1","sensitivity":"1"},{"kind":"type_b_rectangular","half_width":"1","sensitivity":"1"},{"kind":"type_b_rectangular","half_width":"1","sensitivity":"1"}],"coverage_factor":"2","correlation_matrix":[["1","0.9","-0.9"],["0.9","1","0.9"],["-0.9","0.9","1"]]},"adversarial"),
        case("S05","asymmetric",{"components":[{"kind":"type_b_rectangular","half_width":"1","sensitivity":"1"},{"kind":"type_b_rectangular","half_width":"1","sensitivity":"1"}],"coverage_factor":"2","correlation_matrix":[["1","0.5"],["0.4","1"]]},"adversarial"),
        case("S05","out-of-bounds-rho",{"components":[{"kind":"type_b_rectangular","half_width":"1","sensitivity":"1"},{"kind":"type_b_rectangular","half_width":"1","sensitivity":"1"}],"coverage_factor":"2","correlation_matrix":[["1","1.01"],["1.01","1"]]},"adversarial"),
        case("S05","nonunit-diagonal",{"components":[{"kind":"type_b_rectangular","half_width":"1","sensitivity":"1"}],"coverage_factor":"2","correlation_matrix":[["1.0000000000000000001"]]},"adversarial"),
        case("S05","zero-factor",{"components":[{"kind":"type_a","observations":["1","1"],"sensitivity":"1"}],"coverage_factor":"0"},"adversarial"),
        case("S05","negative-half-width",{"components":[{"kind":"type_b_rectangular","half_width":"-1","sensitivity":"1"}],"coverage_factor":"2"},"adversarial"),
        case("S05","one-observation",{"components":[{"kind":"type_a","observations":["1"],"sensitivity":"1"}],"coverage_factor":"2"},"adversarial"),
        case("S05","too-many-components",{"components":[{"kind":"type_b_rectangular","half_width":"1","sensitivity":"1"}]*4,"coverage_factor":"2"},"adversarial"),
    ]
    return out


def make_s06(rng):
    out=[]
    for i in range(20):
        lo=rng.randint(-10,0); hi=rng.randint(1,10); y=rng.randint(lo-3,hi+3); u=rng.choice([0,1,2,3])
        out.append(case("S06",f"seeded-{i:02}",{"y":str(y),"expanded_uncertainty":str(u),"lower_limit":str(lo),"upper_limit":str(hi)}))
    out += [
        case("S06","accept-equality",{"y":"0","expanded_uncertainty":"1","lower_limit":"-1","upper_limit":"1"},"boundary"),
        case("S06","touch-outside-lower",{"y":"0","expanded_uncertainty":"1","lower_limit":"1","upper_limit":"2"},"boundary"),
        case("S06","touch-outside-upper",{"y":"3","expanded_uncertainty":"1","lower_limit":"1","upper_limit":"2"},"boundary"),
        case("S06","reject-below",{"y":"-3","expanded_uncertainty":"1","lower_limit":"0","upper_limit":"2"},"boundary"),
        case("S06","reject-above",{"y":"3","expanded_uncertainty":"1","lower_limit":"0","upper_limit":"2"},"boundary"),
        case("S06","zero-u-at-limit",{"y":"1","expanded_uncertainty":"0","lower_limit":"1","upper_limit":"2"},"boundary"),
        case("S06","negative-u",{"y":"1","expanded_uncertainty":"-0.1","lower_limit":"0","upper_limit":"2"},"adversarial"),
        case("S06","reversed-limits",{"y":"1","expanded_uncertainty":"0.1","lower_limit":"2","upper_limit":"0"},"adversarial"),
        case("S06","wide-indeterminate",{"y":"0","expanded_uncertainty":"100","lower_limit":"-1","upper_limit":"1"},"boundary"),
        case("S06","decimal",{"y":"0.1","expanded_uncertainty":"0.1","lower_limit":"0","upper_limit":"0.2"},"boundary"),
    ]
    return out


def make_s07(rng):
    out=[]
    base={"now_ms":1_800_000_000_000,"timestamp_ms":1_799_999_999_900,"max_age_ms":1000,"allowed_future_skew_ms":100,"sequence":20,"last_sequence":19}
    for i in range(18):
        p=copy.deepcopy(base); p["timestamp_ms"]+=rng.randint(-1100,150); p["sequence"]=(i+21)&0xffffffff; p["last_sequence"]=(i+20)&0xffffffff
        out.append(case("S07",f"seeded-{i:02}",p))
    out += [
        case("S07","stale-boundary",{**base,"timestamp_ms":base["now_ms"]-1000},"boundary"),
        case("S07","stale-before",{**base,"timestamp_ms":base["now_ms"]-1001},"boundary"),
        case("S07","future-boundary",{**base,"timestamp_ms":base["now_ms"]+100},"boundary"),
        case("S07","future-after",{**base,"timestamp_ms":base["now_ms"]+101},"boundary"),
        case("S07","rollover-newer",{**base,"sequence":0,"last_sequence":0xffffffff},"boundary"),
        case("S07","duplicate",{**base,"sequence":10,"last_sequence":10},"adversarial"),
        case("S07","out-of-order",{**base,"sequence":10,"last_sequence":11},"adversarial"),
        case("S07","half-range",{**base,"sequence":0x80000000,"last_sequence":0},"adversarial"),
        case("S07","first",{k:v for k,v in {**base,"sequence":0xffffffff}.items() if k!="last_sequence"},"boundary"),
        case("S07","negative-time",{**base,"timestamp_ms":-1},"adversarial"),
        case("S07","float-time",{**base,"timestamp_ms":1.5},"adversarial"),
        case("S07","bad-sequence",{**base,"sequence":0x100000000},"adversarial"),
        case("S07","negative-age",{**base,"max_age_ms":-1},"adversarial"),
        case("S07","bad-last",{**base,"last_sequence":-1},"adversarial"),
    ]
    return out


def s08_base():
    return {"sensor":{"frame_hex":"19","width_bits":8,"byte_order":"big","signed":False,"scale":"1","rounding_places":0,"sentinel_codes":[]},
        "units":{"from_unit":"C","to_unit":"C"},
        "temporal":{"now_ms":1793491200000,"timestamp_ms":1793491199900,"max_age_ms":1000,"allowed_future_skew_ms":100,"sequence":20,"last_sequence":19},
        "calibration":{"gain":"1","offset":"0","temp_coefficient":"0","ambient_temperature_c":"20","reference_temperature_c":"20","correction_state":"RAW","rounding_places":2},
        "uncertainty":{"components":[{"kind":"type_b_rectangular","half_width":"0.2","sensitivity":"1"}],"coverage_factor":"2"},
        "certificate":cert_base(),"instrument_serial":"SN-17","measurand":"temperature","measurement_date":"2026-11-01","specification":{"lower_limit":"20","upper_limit":"30"}}


def make_s08(rng):
    out=[]
    for i in range(18):
        p=s08_base(); p["sensor"]["frame_hex"]=f"{rng.randint(15,35):02X}"; p["calibration"]["offset"]=str(rng.choice(["0","0.1","-0.1"])); p["uncertainty"]["components"][0]["half_width"]=str(rng.choice(["0.1","0.2","0.3"]))
        out.append(case("S08",f"seeded-{i:02}",p))
    p=s08_base(); p["sensor"].update({"frame_hex":"FF","sentinel_codes":[255]}); out.append(case("S08","sentinel-frame",p,"adversarial"))
    p=s08_base(); p["certificate"]["traceability_chain_status"]="UNKNOWN"; out.append(case("S08","unclear-traceability",p,"adversarial"))
    p=s08_base(); p["certificate"]["serial_number"]="OTHER"; out.append(case("S08","certificate-serial",p,"adversarial"))
    p=s08_base(); p["specification"]={"lower_limit":"20","upper_limit":"25.1"}; out.append(case("S08","indeterminate",p,"boundary"))
    p=s08_base(); p["specification"]={"lower_limit":"20","upper_limit":"24.5"}; out.append(case("S08","reject",p,"boundary"))
    p=s08_base(); p["sensor"]["width_bits"]=16; out.append(case("S08","truncated-frame",p,"adversarial"))
    p=s08_base(); p["calibration"]["temp_coefficient"]="0.1"; p["calibration"]["ambient_temperature_c"]="30"; out.append(case("S08","environment-correction",p,"boundary"))
    p=s08_base(); p["uncertainty"]["coverage_factor"]="0"; out.append(case("S08","uncertainty-invalid",p,"adversarial"))
    p=s08_base(); p["certificate"]["valid_to"]="2026-10-31"; out.append(case("S08","expired-evidence",p,"adversarial"))
    p=s08_base(); p["sensor"].update({"frame_hex":"19","signed":True}); out.append(case("S08","signed-byte",p,"boundary"))
    p=s08_base(); p["calibration"]["correction_state"]="CORRECTED"; out.append(case("S08","double-correction",p,"adversarial"))
    p=s08_base(); p["units"]={"from_unit":"V","to_unit":"C"}; out.append(case("S08","incompatible-units",p,"adversarial"))
    p=s08_base(); p["specification"]={"lower_limit":"24.6","upper_limit":"25.4"}; out.append(case("S08","accept-tight",p,"boundary"))

    # Cross-layer scenarios use declared engineering quantities and simple, checkable math.
    p=s08_base(); p["sensor"].update({"frame_hex":"02A8","width_bits":16,"scale":"0.1","rounding_places":1}); p["units"]={"from_unit":"F","to_unit":"C"}
    p["calibration"].update({"gain":"1.01","offset":"0.1","temp_coefficient":"0.01","ambient_temperature_c":"25","reference_temperature_c":"20"})
    p["uncertainty"]={"components":[{"kind":"type_b_rectangular","half_width":"0.1","sensitivity":"1"},{"kind":"type_b_rectangular","half_width":"0.1","sensitivity":"1"}],"coverage_factor":"2","correlation_matrix":[["1","0.5"],["0.5","1"]]}
    p["certificate"].update({"range_min":"-40","range_max":"125","unit":"C"}); p["specification"]={"lower_limit":"20.1","upper_limit":"20.6"}
    out.append(case("S08","fahrenheit-calibrated-correlated-full-pipeline",p,"integration"))

    p=s08_base(); p["sensor"].update({"frame_hex":"FFCE","width_bits":16,"signed":True,"scale":"0.1","rounding_places":1})
    p["calibration"].update({"temp_coefficient":"0.02","ambient_temperature_c":"25","reference_temperature_c":"20"})
    p["specification"]={"lower_limit":"-5.2","upper_limit":"-4.6"}; p["certificate"].update({"range_min":"-40","range_max":"125"})
    out.append(case("S08","signed-negative-with-environmental-compensation",p,"integration"))

    p=s08_base(); p["uncertainty"]={"components":[{"kind":"type_b_rectangular","half_width":"1","sensitivity":"1"},{"kind":"type_b_rectangular","half_width":"1","sensitivity":"1"}],"coverage_factor":"2","correlation_matrix":[["1","0.5"],["0.5","1"]]}
    p["specification"]={"lower_limit":"22.5","upper_limit":"27.5"}
    out.append(case("S08","two-correlated-rectangular-contributors",p,"integration"))

    # Uncertainty inputs are post-calibration values in final output units.
    p=s08_base(); p["calibration"].update({"gain":"2","offset":"0.5","temp_coefficient":"0.1","ambient_temperature_c":"25","reference_temperature_c":"20"})
    p["uncertainty"]={"components":[{"kind":"type_b_rectangular","half_width":"0.6","sensitivity":"1"}],"coverage_factor":"2"}
    p["specification"]={"lower_limit":"50","upper_limit":"52"}
    out.append(case("S08","uncertainty-supplied-after-calibration-not-rescaled",p,"integration"))

    p=s08_base(); p["calibration"].update({"gain":"1.5","offset":"-0.5","rounding_places":2})
    p["uncertainty"]={"components":[{"kind":"type_a","observations":["49","50","51"],"sensitivity":"1"}],"coverage_factor":"2"}
    p["specification"]={"lower_limit":"35","upper_limit":"39"}
    out.append(case("S08","type-a-observations-already-in-final-unit",p,"integration"))

    p=s08_base(); p["units"]={"from_unit":"C","to_unit":"F"}
    p["calibration"].update({"gain":"1","offset":"0.9","temp_coefficient":"0.2","ambient_temperature_c":"25","reference_temperature_c":"20"})
    p["uncertainty"]={"components":[{"kind":"type_b_rectangular","half_width":"0.3","sensitivity":"1"}],"coverage_factor":"2"}
    p["certificate"].update({"range_min":"32","range_max":"212","unit":"F"})
    p["specification"]={"lower_limit":"78","upper_limit":"80"}
    out.append(case("S08","fahrenheit-output-units-and-celsius-temperature-interval",p,"integration"))

    p=s08_base(); p["sensor"].update({"frame_hex":"09C4","width_bits":16,"scale":"0.01","rounding_places":2})
    p["calibration"].update({"gain":"1.02","offset":"0.1"})
    p["uncertainty"]={"components":[{"kind":"type_b_rectangular","half_width":"0.4330127018922193233818615853764680917357","sensitivity":"1"}],"coverage_factor":"2"}
    p["specification"]={"lower_limit":"20","upper_limit":"26.1"}
    out.append(case("S08","calibrated-result-touches-upper-conformity-boundary",p,"boundary"))

    for name,reading in (("calibration-range-inclusive-low",0),("calibration-range-inclusive-high",40)):
        p=s08_base(); p["sensor"].update({"frame_hex":f"{reading:02X}","rounding_places":0}); p["certificate"].update({"range_min":"0","range_max":"40"})
        p["uncertainty"]={"components":[{"kind":"type_b_rectangular","half_width":"0.1","sensitivity":"1"}],"coverage_factor":"2"}
        p["specification"]={"lower_limit":str(reading-1),"upper_limit":str(reading+1)}
        out.append(case("S08",name,p,"boundary"))
    for name,reading in (("calibration-range-exclusive-below",-1),("calibration-range-exclusive-above",4001)):
        p=s08_base(); p["sensor"].update({"frame_hex":encode_register_count(reading,16,"big",True),"width_bits":16,"signed":True,"scale":"0.01","rounding_places":2}); p["certificate"].update({"range_min":"0","range_max":"40"})
        p["uncertainty"]={"components":[{"kind":"type_b_rectangular","half_width":"0.1","sensitivity":"1"}],"coverage_factor":"2"}
        p["specification"]={"lower_limit":"-5","upper_limit":"45"}
        out.append(case("S08",name,p,"adversarial"))

    p=s08_base(); p["temporal"].update({"timestamp_ms":1793491198999,"max_age_ms":1000})
    p["certificate"].update({"range_min":"-40","range_max":"125"})
    out.append(case("S08","valid-certificate-with-stale-sensor-data",p,"adversarial"))

    p=s08_base(); p["temporal"].update({"timestamp_ms":1793491198999,"max_age_ms":1000})
    p["uncertainty"]={"components":[{"kind":"type_b_rectangular","half_width":"-0.1","sensitivity":"1"}],"coverage_factor":"2"}
    p["certificate"].update({"status":"EXPIRED","valid_to":"2026-10-31","traceability_chain_status":"UNKNOWN","range_min":"-40","range_max":"125"})
    out.append(case("S08","stale-invalid-uncertainty-and-invalid-certificate",p,"adversarial"))

    p=s08_base(); p["temporal"].pop("last_sequence")
    p["temporal"].update({"sequence":0,"now_ms":1793491200000,"timestamp_ms":1793491200000})
    p["certificate"].update({"range_min":"-40","range_max":"125"})
    out.append(case("S08","first-packet-at-rollover-boundary",p,"boundary"))
    return out


BUILDERS={"S01":make_s01,"S02":make_s02,"S03":make_s03,"S04":make_s04,"S05":make_s05,"S06":make_s06,"S07":make_s07,"S08":make_s08}


def main():
    for index,(code,builder) in enumerate(BUILDERS.items(),1):
        seed=MASTER_SEED+index*1009
        cases=builder(random.Random(seed))
        if len(cases)<25: raise RuntimeError(f"{code} has only {len(cases)} cases")
        for item in cases:
            item["expected"]=SOLVERS[code](item["input"])
        path=ROOT/"graders"/"hidden"/f"{code}.json"
        path.write_text(json.dumps({"task":code,"master_seed":MASTER_SEED,"task_seed":seed,"cases":cases},indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print(f"{code}: {len(cases)} deterministic cases (seed {seed}) -> {path.relative_to(ROOT)}")


if __name__=="__main__": main()
