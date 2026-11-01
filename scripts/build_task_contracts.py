"""Materialize agent-visible task contracts, schemas, and starter repositories."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TASKS = {
"S01": ("raw_sensor_interpretation", "Raw Sensor Interpretation", "Decode one complete fixed-width register frame into a signed or unsigned count and scaled physical value.",
"The frame is exactly width_bits/8 bytes represented by hexadecimal text; ASCII spaces and underscores are ignored. Supported widths are 8, 16, 24, or 32 bits. byte_order is `big` or `little`. signed selects two's-complement interpretation. sentinel_codes are in-range unsigned bit-pattern values checked before signed interpretation. scale is a strictly positive exact decimal multiplier; value=count*scale. rounding_places is 0..12 and output rounding is decimal ROUND_HALF_EVEN. Reject malformed, truncated, overlong, or sentinel frames. A valid output is {valid:true,raw_count:integer,value:decimal-string}; errors are {valid:false,reason:code}. Error codes: invalid_width, invalid_byte_order, invalid_frame, frame_length, invalid_sentinels, sentinel, invalid_signed_flag, invalid_scale, invalid_parameters. No register offsets or implicit defaults are allowed except sentinel_codes defaults to [].", ["frame_hex", "width_bits", "byte_order", "signed", "scale", "rounding_places"],
{"frame_hex":"FFFE","width_bits":16,"byte_order":"big","signed":True,"scale":"0.01","rounding_places":2,"sentinel_codes":[]}),
"S02": ("physical_unit_integrity", "Physical Unit Integrity", "Convert only within a named physical quantity using exact contract-defined affine transforms.",
"Supported temperature units are C, F, K; pressure units Pa, kPa, bar; voltage units V, mV. Convert source to canonical C/Pa/V and then target. Exact definitions: F→C=(F−32)*5/9, K→C=K−273.15; kPa→Pa=1000*kPa, bar→Pa=100000*bar; mV→V=mV/1000. Reverse transforms are algebraic inverses. Same-unit conversion is identity. Never infer units; reject unknown or incompatible pairs. Decimal input is a JSON decimal string or integer, not binary float. Output is rounded to rounding_places (0..12) using ROUND_HALF_EVEN and includes the requested unit. Return {valid:false,reason:incompatible_or_unknown_unit} for unknown/incompatible units and invalid_parameters for malformed decimals or precision.", ["value", "from_unit", "to_unit", "rounding_places"],
{"value":"32","from_unit":"F","to_unit":"C","rounding_places":2}),
"S03": ("calibration_environmental_compensation", "Calibration and Environmental Compensation", "Apply the declared affine calibration and temperature compensation exactly once.",
"Compute corrected = gain*raw_value + offset + temp_coefficient*(ambient_temperature_c-reference_temperature_c), in that order. This task uses the explicit symbolic measurand unit `MU`: raw_value, offset, and corrected_value are MU; temp_coefficient is MU/°C; both temperatures are °C; gain is dimensionless. `MU` is a benchmark unit label, not a claim that the quantity is SI or a particular real-world unit. All coefficients and inputs are exact decimal strings or integers. correction_state must equal RAW; any other state is rejected as already_corrected. Coefficients are all required, finite; no defaults. Output rounds by ROUND_HALF_EVEN to rounding_places 0..12. Return {valid:false,reason:already_corrected} for another correction state, invalid_gain for gain<=0, and invalid_parameters for malformed, missing, or nonfinite values or precision.", ["raw_value", "gain", "offset", "temp_coefficient", "ambient_temperature_c", "reference_temperature_c", "correction_state", "rounding_places"],
{"raw_value":"10","gain":"1.02","offset":"-0.1","temp_coefficient":"0.01","ambient_temperature_c":"30","reference_temperature_c":"20","correction_state":"RAW","rounding_places":3}),
"S04": ("calibration_applicability_validity", "Calibration Applicability and Validity", "Check whether synthetic calibration evidence applies to one measurement under explicit task rules.",
"Check serial, measurand, CURRENT status, exact YYYY-MM-DD validity dates (inclusive), inclusive measurement range, finite nonnegative uncertainty, exact unit, and DOCUMENTED traceability. Collect every independently checkable reason in fixed order: missing certificate fields in serial_number, measurand, status, valid_from, valid_to, range_min, range_max, uncertainty, unit, traceability_chain_status order; serial_mismatch; measurand_mismatch; calibration_not_current; invalid_validity_interval; outside_validity_dates; invalid_date; invalid_range; outside_calibration_range; invalid_range_or_value; invalid_uncertainty or missing_or_invalid_uncertainty; unit_mismatch; traceability_not_documented. Skip checks requiring absent certificate values; a separately malformed measurement date/value remains reportable. A missing certificate field is not duplicated as malformed. Malformed outer objects return invalid_structure. DOCUMENTED is synthetic evidence only and establishes neither accreditation nor legal compliance.", ["certificate", "measurement"],
{"certificate":{"serial_number":"SN-17","measurand":"temperature","status":"CURRENT","valid_from":"2026-01-01","valid_to":"2026-12-31","range_min":"-20","range_max":"100","uncertainty":"0.2","unit":"C","traceability_chain_status":"DOCUMENTED"},"measurement":{"serial_number":"SN-17","measurand":"temperature","date":"2026-11-01","value":"25","unit":"C"}}),
"S05": ("measurement_uncertainty", "Measurement Uncertainty Propagation", "Evaluate Type A and Type B standard uncertainties and propagate them through a linear measurement model.",
"Provide 1..3 components. Every observation and half_width is expressed in one shared symbolic task unit `MU`; sensitivity coefficients are dimensionless, and every reported standard uncertainty is MU. `MU` is a benchmark unit label, not a claim that the measurand is SI or a particular real-world quantity. Type A component observations must contain >=2 finite decimal values; standard uncertainty of the mean is sample standard deviation (ddof=1) divided by sqrt(n). Type B kind `type_b_rectangular` supplies nonnegative symmetric half_width a; u=a/sqrt(3). Every component has a sensitivity coefficient. If correlation_matrix is omitted, and only then, use identity. If supplied, require a square n×n symmetric matrix, exact diagonal 1, coefficients in [-1,1], and positive semidefinite (all principal minors nonnegative within 1e-24). cov(i,j)=rho(i,j)*u_i*u_j. Calculate uc²=sum(c_i²u_i²)+2 sum(i<j)c_i*c_j*cov(i,j); reject materially negative variance. coverage_factor k must be finite and >0; U=k*uc. Use Decimal arithmetic, 40-digit working precision, report decimal strings. Grading tolerance: 1e-16 MU absolute for uncertainty outputs; component validity/status and list lengths are exact. Errors return {valid:false,reason:code}; codes: unsupported_component_count, type_a_requires_two_observations, negative_half_width, invalid_component_kind, invalid_correlation_shape, invalid_correlation_diagonal, invalid_correlation_matrix, non_psd_correlation_matrix, negative_propagated_variance, invalid_coverage_factor, invalid_parameters. This is the specified linear propagation model, not an assertion that all uncertainty sources in practice fit it.", ["components", "coverage_factor"],
{"components":[{"kind":"type_a","observations":["9.9","10.0","10.1"],"sensitivity":"1"},{"kind":"type_b_rectangular","half_width":"0.3","sensitivity":"2"}],"coverage_factor":"2","correlation_matrix":[["1","0"],["0","1"]]}),
"S06": ("conformity_decisions", "Conformity and Engineering Decisions", "Apply the specified conservative interval decision rule, including equality boundaries.",
"Given finite decimal y, expanded_uncertainty U, lower_limit L and upper_limit H, require U>=0 and L<=H. All four values use the same explicit symbolic task unit `MU`; this label is not a claim that the measured quantity is SI or a particular real-world unit. Form [y-U,y+U]. ACCEPT iff y-U>=L and y+U<=H; REJECT iff y+U<L or y-U>H (strict disjointness); otherwise INDETERMINATE. Thus equality at both specification limits is ACCEPT when the complete interval remains inside; an uncertainty interval merely touching a limit from outside is INDETERMINATE. Never substitute another guard-band rule. Return valid, interval endpoints, and one exact decision string. Errors return {valid:false,reason:negative_uncertainty|malformed_limits|invalid_parameters}.", ["y", "expanded_uncertainty", "lower_limit", "upper_limit"],
{"y":"10","expanded_uncertainty":"0.5","lower_limit":"9","upper_limit":"11"}),
"S07": ("temporal_data_integrity", "Temporal and Data Integrity", "Check one timestamp and uint32 sequence number against current time and an optional last sequence.",
"Timestamps are nonnegative integer Unix UTC milliseconds. now_ms uses the same scale. timestamp is stale only when timestamp_ms < now_ms-max_age_ms; future only when timestamp_ms > now_ms+allowed_future_skew_ms. Both boundaries are valid. age and skew must be nonnegative integers. sequence and optional last_sequence are uint32 integers. Validate required-field and timestamp/age/skew/sequence types and ranges first (invalid_timestamp_or_parameters); then check future timestamp, stale timestamp, optional last_sequence validity (invalid_last_sequence), and finally sequence disposition. Compare delta=(sequence-last_sequence) mod 2^32: delta=0 is duplicate_sequence; 1..2^31-1 is NEWER; delta=2^31 is ambiguous_half_range; 2^31+1..2^32-1 is out_of_order_sequence. Missing/null last_sequence means FIRST. Return {valid:true,reason:first_sequence|ok,sequence_order:FIRST|NEWER} or {valid:false,reason:future_timestamp|stale_timestamp|duplicate_sequence|ambiguous_half_range|out_of_order_sequence|invalid_timestamp_or_parameters|invalid_last_sequence|invalid_structure}.", ["timestamp_ms", "now_ms", "max_age_ms", "allowed_future_skew_ms", "sequence"],
{"timestamp_ms":100000,"now_ms":100100,"max_age_ms":1000,"allowed_future_skew_ms":50,"sequence":0,"last_sequence":4294967295}),
"S08": ("end_to_end_integrity", "End-to-End Measurement Integrity", "Preserve the meaning of one synthetic measurement through decoding, conversion, calibration, uncertainty, evidence checks, and conformity.",
"The processing order is exact: (1) decode the register frame and scale into the sensor's declared `units.from_unit`; S01's `sensor.rounding_places` is applied here. Return `decoded_measurement` as `{raw_count, value, unit}` and set `unit` exactly to `units.from_unit`. (2) Convert that decoded value from `from_unit` to `to_unit` using S02's explicit affine rules; `physical_quantity.unit` must equal `to_unit`; no other unit conversion is inferred and conversion is not rounded again. (3) Apply `corrected = gain * physical_value + offset + temp_coefficient * (ambient_temperature_c - reference_temperature_c)` once. `gain` is dimensionless. `offset` is expressed in final `to_unit`; `temp_coefficient` is `to_unit` per degree Celsius. Both temperature inputs are in °C and their difference is a Celsius temperature interval; do not convert that interval to °F or K. `corrected_measurement.unit` must equal `to_unit`. The corrected result is rounded only by `calibration.rounding_places`. (4) The S05 uncertainty budget is supplied after calibration: every Type A observation and Type B half-width is already expressed in final `to_unit`. Sensitivity coefficients are dimensionless. Do not scale these uncertainty inputs by calibration gain or by the input-to-output unit conversion. `cov(i,j)=rho(i,j)*u_i*u_j` has unit `to_unit²`; combined standard and expanded uncertainty have unit `to_unit`. (5) Check S04 evidence using the corrected value, `to_unit`, serial, measurand and date. (6) Apply S06 to the corrected value, expanded uncertainty and specification limits; both limits are in `to_unit`, and the uncertainty interval uses the inclusive decision rule specified by S06. A worked Celsius-input/Fahrenheit-output example has decoded 25 °C → physical 77 °F; with gain 1, offset 0.9 °F, temperature coefficient 0.2 °F/°C and a +5 °C temperature interval, the corrected result is 78.9 °F. A post-calibration Type B half-width of 0.3 °F is not multiplied by gain. The required temporal object contains now_ms, timestamp_ms, max_age_ms, allowed_future_skew_ms, sequence, and optional last_sequence. Retain independent temporal, uncertainty and certificate checks when another independent stage fails. A missing corrected value makes certificate range applicability unavailable. Any failed stage leaves valid=false and conformity_decision=INDETERMINATE; no conformity interval is emitted unless all stages are valid. Error ordering is decode, temporal, units, calibration, uncertainty, certificate reason order, conformity, pipeline. Certificate uncertainty remains evidence only and is not combined into the supplied budget because its type/coverage/correlation are not given. Synthetic traceability implies no accreditation or legal compliance.", ["sensor", "temporal", "units", "calibration", "uncertainty", "certificate", "instrument_serial", "measurand", "measurement_date", "specification"],
{"sensor":{"frame_hex":"19","width_bits":8,"byte_order":"big","signed":False,"scale":"1","rounding_places":0,"sentinel_codes":[]},"units":{"from_unit":"C","to_unit":"C"},"temporal":{"now_ms":1793491200000,"timestamp_ms":1793491199900,"max_age_ms":1000,"allowed_future_skew_ms":100,"sequence":20,"last_sequence":19},"calibration":{"gain":"1","offset":"0","temp_coefficient":"0","ambient_temperature_c":"20","reference_temperature_c":"20","correction_state":"RAW","rounding_places":2},"uncertainty":{"components":[{"kind":"type_b_rectangular","half_width":"0.3","sensitivity":"1"}],"coverage_factor":"2"},"certificate":{"serial_number":"S-1","measurand":"temperature","status":"CURRENT","valid_from":"2026-01-01","valid_to":"2026-12-31","range_min":"0","range_max":"100","uncertainty":"0.2","unit":"C","traceability_chain_status":"DOCUMENTED"},"instrument_serial":"S-1","measurand":"temperature","measurement_date":"2026-11-01","specification":{"lower_limit":"20","upper_limit":"30"}})
}


DEC = {"oneOf": [{"type": "string", "pattern": "^-?[0-9]+(\\.[0-9]+)?$"}, {"type": "integer"}]}
INT = {"type": "integer"}
STR = {"type": "string"}
BOOL = {"type": "boolean"}


def obj(required, properties, additional=False):
    return {"type": "object", "required": required, "properties": properties, "additionalProperties": additional}


def _schema_for(code):
    if code == "S08":
        temporal = obj(["now_ms","timestamp_ms","max_age_ms","allowed_future_skew_ms","sequence"], {"now_ms":{"type":"integer","minimum":0},"timestamp_ms":{"type":"integer","minimum":0},"max_age_ms":{"type":"integer","minimum":0},"allowed_future_skew_ms":{"type":"integer","minimum":0},"sequence":{"type":"integer","minimum":0,"maximum":4294967295},"last_sequence":{"oneOf":[{"type":"null"},{"type":"integer","minimum":0,"maximum":4294967295}]}})
        units = obj(["from_unit","to_unit"],{"from_unit":{"enum":["C","F","K","Pa","kPa","bar","V","mV"]},"to_unit":{"enum":["C","F","K","Pa","kPa","bar","V","mV"]}})
        units["description"] = "Decode in from_unit, then convert exactly once to to_unit before calibration."
        calibration = _schema_for("S03")
        calibration["description"] = "gain dimensionless; offset in to_unit; temp_coefficient in to_unit per degree Celsius; temperature difference is computed in Celsius."
        uncertainty = _schema_for("S05")
        uncertainty["description"] = "All observations and half-widths are post-calibration values in to_unit; sensitivities are dimensionless; covariance has to_unit squared."
        return {"$schema":"https://json-schema.org/draft/2020-12/schema", **obj(["sensor","temporal","units","calibration","uncertainty","certificate","instrument_serial","measurand","measurement_date","specification"], {"sensor":_schema_for("S01"),"temporal":temporal,"units":units,"calibration":calibration,"uncertainty":uncertainty,"certificate":_schema_for("S04")["properties"]["certificate"],"instrument_serial":STR,"measurand":STR,"measurement_date":STR,"specification":obj(["lower_limit","upper_limit"],{"lower_limit":DEC,"upper_limit":DEC})})}
    schemas = {
    "S01": obj(["frame_hex","width_bits","byte_order","signed","scale","rounding_places"], {"frame_hex":STR,"width_bits":{"enum":[8,16,24,32]},"byte_order":{"enum":["big","little"]},"signed":BOOL,"scale":DEC,"rounding_places":{"type":"integer","minimum":0,"maximum":12},"sentinel_codes":{"type":"array","items":{"type":"integer","minimum":0}}}),
    "S02": obj(["value","from_unit","to_unit","rounding_places"], {"value":DEC,"from_unit":{"enum":["C","F","K","Pa","kPa","bar","V","mV"]},"to_unit":{"enum":["C","F","K","Pa","kPa","bar","V","mV"]},"rounding_places":{"type":"integer","minimum":0,"maximum":12}}),
    "S03": obj(["raw_value","gain","offset","temp_coefficient","ambient_temperature_c","reference_temperature_c","correction_state","rounding_places"], {"raw_value":DEC,"gain":DEC,"offset":DEC,"temp_coefficient":DEC,"ambient_temperature_c":DEC,"reference_temperature_c":DEC,"correction_state":{"enum":["RAW"]},"rounding_places":{"type":"integer","minimum":0,"maximum":12}}),
    "S04": obj(["certificate","measurement"], {"certificate":obj(["serial_number","measurand","status","valid_from","valid_to","range_min","range_max","uncertainty","unit","traceability_chain_status"], {"serial_number":STR,"measurand":STR,"status":STR,"valid_from":STR,"valid_to":STR,"range_min":DEC,"range_max":DEC,"uncertainty":DEC,"unit":STR,"traceability_chain_status":STR}),"measurement":obj(["serial_number","measurand","date","value","unit"], {"serial_number":STR,"measurand":STR,"date":STR,"value":DEC,"unit":STR})}),
    "S05": obj(["components","coverage_factor"], {"components":{"type":"array","minItems":1,"maxItems":3,"items":{"oneOf":[obj(["kind","observations","sensitivity"],{"kind":{"const":"type_a"},"observations":{"type":"array","minItems":2,"items":DEC},"sensitivity":DEC}),obj(["kind","half_width","sensitivity"],{"kind":{"const":"type_b_rectangular"},"half_width":DEC,"sensitivity":DEC})]}},"coverage_factor":DEC,"correlation_matrix":{"type":"array","items":{"type":"array","items":DEC}}}),
    "S06": obj(["y","expanded_uncertainty","lower_limit","upper_limit"], {"y":DEC,"expanded_uncertainty":DEC,"lower_limit":DEC,"upper_limit":DEC}),
    "S07": obj(["timestamp_ms","now_ms","max_age_ms","allowed_future_skew_ms","sequence"], {"timestamp_ms":INT,"now_ms":INT,"max_age_ms":INT,"allowed_future_skew_ms":INT,"sequence":{"type":"integer","minimum":0,"maximum":4294967295},"last_sequence":{"oneOf":[{"type":"null"},{"type":"integer","minimum":0,"maximum":4294967295}]}}),
    }
    return {"$schema":"https://json-schema.org/draft/2020-12/schema", **schemas[code]}


def _output_schema(code):
    def result(success, error, required_success, props_success, extra_success=False):
        props = {"valid":{"const":True}, **props_success}
        success_s = obj(["valid",*required_success], props, extra_success)
        err_s = obj(["valid","reason"], {"valid":{"const":False},"reason":STR}, False)
        return {"$schema":"https://json-schema.org/draft/2020-12/schema","oneOf":[success_s,err_s]}
    num={"type":"string","pattern":"^-?[0-9]+(\\.[0-9]+)?$"}
    reason={"type":"string"}
    if code=="S01": return result(True,True,["raw_count","value"],{"raw_count":INT,"value":num})
    if code=="S02": return result(True,True,["value","unit"],{"value":num,"unit":STR})
    if code=="S03": return result(True,True,["corrected_value"],{"corrected_value":num})
    if code=="S04": return {"$schema":"https://json-schema.org/draft/2020-12/schema",**obj(["valid","reasons"],{"valid":BOOL,"reasons":{"type":"array","items":reason}})}
    if code=="S05":
        ok=obj(["valid","standard_uncertainties","combined_standard_uncertainty","expanded_uncertainty"],{"valid":{"const":True},"standard_uncertainties":{"type":"array","items":num},"combined_standard_uncertainty":num,"expanded_uncertainty":num},False)
        err=obj(["valid","reason"],{"valid":{"const":False},"reason":STR},False)
        return {"$schema":"https://json-schema.org/draft/2020-12/schema","oneOf":[ok,err]}
    if code=="S06": return result(True,True,["lower","upper","decision"],{"lower":num,"upper":num,"decision":{"enum":["ACCEPT","REJECT","INDETERMINATE"]}})
    if code=="S07":
        ok=obj(["valid","reason","sequence_order"],{"valid":{"const":True},"reason":STR,"sequence_order":{"enum":["FIRST","NEWER"]}},False)
        err=obj(["valid","reason"],{"valid":{"const":False},"reason":STR},False)
        return {"$schema":"https://json-schema.org/draft/2020-12/schema","oneOf":[ok,err]}
    if code=="S08":
        nullable_num={"oneOf":[num,{"type":"null"}]}
        decoded={"description":"Reported in units.from_unit exactly as decoded and scaled from the sensor frame.","oneOf":[obj(["raw_count","value","unit"],{"raw_count":INT,"value":num,"unit":STR}),{"type":"null"}]}
        physical={"description":"Reported in the canonical requested units.to_unit.","oneOf":[obj(["value","unit"],{"value":num,"unit":STR}),{"type":"null"}]}
        corrected={"description":"Calibration is applied after unit conversion; reported in units.to_unit.","oneOf":[obj(["value","unit"],{"value":num,"unit":STR}),{"type":"null"}]}
        props={"valid":BOOL,"decoded_measurement":decoded,"physical_quantity":physical,"corrected_measurement":corrected,"temporal_validity":obj(["valid","reason"],{"valid":BOOL,"reason":STR,"sequence_order":{"enum":["FIRST","NEWER"]}}),"calibration_validity":obj(["valid","reasons"],{"valid":BOOL,"reasons":{"type":"array","items":STR}}),"standard_uncertainty":nullable_num,"expanded_uncertainty":nullable_num,"conformity_decision":{"enum":["ACCEPT","REJECT","INDETERMINATE"]},"error_reasons":{"type":"array","items":STR},"conformity_interval":obj(["lower","upper"],{"lower":num,"upper":num})}
        return {"$schema":"https://json-schema.org/draft/2020-12/schema",**obj(["valid","decoded_measurement","physical_quantity","corrected_measurement","temporal_validity","calibration_validity","standard_uncertainty","expanded_uncertainty","conformity_decision","error_reasons"],props,False),"allOf":[{"if":{"properties":{"valid":{"const":True}}},"then":{"required":["conformity_interval"]}}]}


def _public_inputs(code, base):
    import copy
    if code=="S01": return [base,{"frame_hex":"3412","width_bits":16,"byte_order":"little","signed":False,"scale":"0.1","rounding_places":1},{"frame_hex":"FF","width_bits":8,"byte_order":"big","signed":False,"scale":"1","rounding_places":0,"sentinel_codes":[255]}]
    if code=="S02": return [base,{"value":"101325","from_unit":"Pa","to_unit":"kPa","rounding_places":2},{"value":"2500","from_unit":"mV","to_unit":"V","rounding_places":3}]
    if code=="S03": return [base,{"raw_value":"4","gain":"2","offset":"1","temp_coefficient":"0.5","ambient_temperature_c":"30","reference_temperature_c":"20","correction_state":"RAW","rounding_places":3},{"raw_value":"0","gain":"1","offset":"0","temp_coefficient":"0","ambient_temperature_c":"-40","reference_temperature_c":"20","correction_state":"RAW","rounding_places":1}]
    if code=="S04":
        at_min=copy.deepcopy(base); at_min["measurement"]["value"]="-20"
        at_date=copy.deepcopy(base); at_date["measurement"]["date"]="2026-01-01"
        return [base,at_min,at_date]
    if code=="S05": return [base,{"components":[{"kind":"type_b_rectangular","half_width":"1","sensitivity":"1"}],"coverage_factor":"2"},{"components":[{"kind":"type_b_rectangular","half_width":"1","sensitivity":"1"},{"kind":"type_b_rectangular","half_width":"2","sensitivity":"1"}],"coverage_factor":"2","correlation_matrix":[["1","0.5"],["0.5","1"]]}]
    if code=="S06": return [base,{"y":"0","expanded_uncertainty":"1","lower_limit":"-1","upper_limit":"1"},{"y":"5","expanded_uncertainty":"0.5","lower_limit":"0","upper_limit":"4"}]
    if code=="S07": return [base,{"timestamp_ms":100000,"now_ms":100000,"max_age_ms":1000,"allowed_future_skew_ms":0,"sequence":0,"last_sequence":4294967295},{"timestamp_ms":98999,"now_ms":100000,"max_age_ms":1000,"allowed_future_skew_ms":0,"sequence":1,"last_sequence":0}]
    if code=="S08":
        base["temporal"]={"now_ms":1793491200000,"timestamp_ms":1793491199900,"max_age_ms":1000,"allowed_future_skew_ms":100,"sequence":20,"last_sequence":19}
        fahrenheit_input=copy.deepcopy(base)
        fahrenheit_input["sensor"].update({"frame_hex":"02A8","width_bits":16,"scale":"0.1","rounding_places":1})
        fahrenheit_input["units"]={"from_unit":"F","to_unit":"C"}
        fahrenheit_input["calibration"].update({"gain":"1.01","offset":"0.1","temp_coefficient":"0.01","ambient_temperature_c":"25","reference_temperature_c":"20"})
        fahrenheit_input["uncertainty"]={"components":[{"kind":"type_b_rectangular","half_width":"0.1","sensitivity":"1"},{"kind":"type_b_rectangular","half_width":"0.1","sensitivity":"1"}],"coverage_factor":"2","correlation_matrix":[["1","0.5"],["0.5","1"]]}
        fahrenheit_input["certificate"].update({"range_min":"-40","range_max":"125","unit":"C"})
        fahrenheit_input["specification"]={"lower_limit":"20.1","upper_limit":"20.6"}

        fahrenheit_output=copy.deepcopy(base)
        fahrenheit_output["units"]={"from_unit":"C","to_unit":"F"}
        fahrenheit_output["calibration"].update({"gain":"1","offset":"0.9","temp_coefficient":"0.2","ambient_temperature_c":"25","reference_temperature_c":"20"})
        fahrenheit_output["uncertainty"]={"components":[{"kind":"type_b_rectangular","half_width":"0.3","sensitivity":"1"}],"coverage_factor":"2"}
        fahrenheit_output["certificate"].update({"range_min":"32","range_max":"212","unit":"F"})
        fahrenheit_output["specification"]={"lower_limit":"78","upper_limit":"80"}

        post_cal_uncertainty=copy.deepcopy(base)
        post_cal_uncertainty["calibration"].update({"gain":"2","offset":"0.5","temp_coefficient":"0.1","ambient_temperature_c":"25","reference_temperature_c":"20"})
        post_cal_uncertainty["uncertainty"]={"components":[{"kind":"type_b_rectangular","half_width":"0.6","sensitivity":"1"}],"coverage_factor":"2"}
        post_cal_uncertainty["specification"]={"lower_limit":"50","upper_limit":"52"}

        type_a_post_cal=copy.deepcopy(base)
        type_a_post_cal["calibration"].update({"gain":"1.5","offset":"-0.5","rounding_places":2})
        type_a_post_cal["uncertainty"]={"components":[{"kind":"type_a","observations":["49","50","51"],"sensitivity":"1"}],"coverage_factor":"2"}
        type_a_post_cal["specification"]={"lower_limit":"35","upper_limit":"39"}

        indeterminate=copy.deepcopy(base); indeterminate["specification"]={"lower_limit":"20","upper_limit":"25.1"}
        reject=copy.deepcopy(base); reject["specification"]={"lower_limit":"20","upper_limit":"24.5"}
        return [base,fahrenheit_input,fahrenheit_output,post_cal_uncertainty,type_a_post_cal,indeterminate,reject]
    return [base]


def main():
    import sys
    sys.path.insert(0, str(ROOT))
    from oracle.compute import SOLVERS
    for code, (slug, title, summary, details, required, example) in TASKS.items():
        folder = ROOT / "tasks" / f"{code}_{slug}"
        folder.mkdir(parents=True, exist_ok=True)
        spec = f"# {code} — {title}\n\n## Problem\n\n{summary}\n\n## Complete specification\n\n{details}\n\n## Interface\n\nImplement exactly `def solve(payload: dict) -> dict` in `solution.py`. Input and output use JSON objects. Do not read files outside this task workspace or assume hidden-test values. Preserve explicit errors; do not silently default required parameters. Public examples and their expected outputs are in `public_examples.json`.\n\n## Grading contract\n\nThe grader checks schema and exact validity/disposition fields, then checks every numeric field using task-specific absolute tolerances documented in the grading methodology. Invalid-input cases are part of the score. Hidden tests are deterministic and remain outside this exported workspace.\n"
        (folder / "task.md").write_text(spec, encoding="utf-8")
        input_schema = _schema_for(code)
        if code == "S08":
            input_schema["properties"]["calibration"]["required"].remove("raw_value")
            input_schema["properties"]["calibration"]["properties"].pop("raw_value")
        (folder / "input.schema.json").write_text(json.dumps(input_schema, indent=2)+"\n", encoding="utf-8")
        (folder / "output.schema.json").write_text(json.dumps(_output_schema(code), indent=2)+"\n", encoding="utf-8")
        public=[{"input":item,"expected":SOLVERS[code](item)} for item in _public_inputs(code,example)]
        (folder / "public_examples.json").write_text(json.dumps(public, indent=2)+"\n", encoding="utf-8")
        (folder / "solution.py").write_text('"""Starter implementation. Complete solve(payload) per task.md."""\n\ndef solve(payload: dict) -> dict:\n    raise NotImplementedError("Implement the task contract")\n', encoding="utf-8")


if __name__ == "__main__": main()
