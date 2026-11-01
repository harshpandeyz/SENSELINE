"""Independent expected-result implementation for deterministic grading.

This intentionally does not import reference implementations. It uses separate
decoding, conversion, variance, and interval code paths to reduce correlated bugs.
"""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
from itertools import permutations, combinations
from fractions import Fraction


def D(v):
    if isinstance(v, bool) or isinstance(v, float):
        raise ValueError("bad decimal")
    d = Decimal(str(v))
    if not d.is_finite():
        raise ValueError("nonfinite")
    return d


def F(d):
    s = format(d, "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


def Q(d, places):
    if isinstance(places, bool) or not isinstance(places, int) or places < 0 or places > 12:
        raise ValueError("bad precision")
    return format(d.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN), f".{places}f")


def bad(reason):
    return {"valid": False, "reason": reason}


def _decode(p):
    try:
        bits = p["width_bits"]
        if isinstance(bits, bool) or bits not in (8, 16, 24, 32): return bad("invalid_width")
        if p["byte_order"] not in ("big", "little"): return bad("invalid_byte_order")
        token = p["frame_hex"]
        if not isinstance(token, str): return bad("invalid_frame")
        compact = token.replace(" ", "").replace("_", "")
        if any(char not in "0123456789abcdefABCDEF" for char in compact): return bad("invalid_frame")
        if len(compact) % 2: return bad("invalid_frame")
        try: octets = [int(compact[i:i+2], 16) for i in range(0, len(compact), 2)]
        except ValueError: return bad("invalid_frame")
        if len(octets) != bits // 8: return bad("frame_length")
        if p["byte_order"] == "little": octets.reverse()
        magnitude = 0
        for octet in octets: magnitude = magnitude * 256 + octet
        sentinels = p.get("sentinel_codes", [])
        if not isinstance(sentinels, list) or any(isinstance(x, bool) or not isinstance(x, int) for x in sentinels): return bad("invalid_sentinels")
        if any(x < 0 or x >= (1 << bits) for x in sentinels): return bad("invalid_sentinels")
        if magnitude in sentinels: return bad("sentinel")
        if not isinstance(p["signed"], bool): return bad("invalid_signed_flag")
        number = magnitude - (1 << bits) if p["signed"] and magnitude >= (1 << (bits - 1)) else magnitude
        scale=D(p["scale"])
        if scale <= 0: return bad("invalid_scale")
        with localcontext() as ctx:
            ctx.prec=80
            return {"valid": True, "raw_count": number, "value": Q(D(number) * scale, p["rounding_places"])}
    except (KeyError, ValueError, TypeError, InvalidOperation): return bad("invalid_parameters")


_SCALE = {"C": (Fraction(1), Fraction(0)), "F": (Fraction(5,9), Fraction(-160,9)), "K": (Fraction(1), Fraction(-27315,100)),
          "Pa": (Fraction(1), Fraction(0)), "kPa": (Fraction(1000), Fraction(0)), "bar": (Fraction(100000), Fraction(0)),
          "V": (Fraction(1), Fraction(0)), "mV": (Fraction(1,1000), Fraction(0))}
_FAMILY = {"C": 0, "F": 0, "K": 0, "Pa": 1, "kPa": 1, "bar": 1, "V": 2, "mV": 2}


def _convert(p):
    try:
        src, dst = p["from_unit"], p["to_unit"]
        if src not in _SCALE or dst not in _SCALE or _FAMILY[src] != _FAMILY[dst]: return bad("incompatible_or_unknown_unit")
        with localcontext() as ctx:
            ctx.prec=80
            answer = _convert_value(D(p["value"]), src, dst)
            return {"valid": True, "value": Q(answer, p["rounding_places"]), "unit": dst}
    except (KeyError, ValueError, TypeError, InvalidOperation, ArithmeticError): return bad("invalid_parameters")


def _convert_value(value, src, dst):
    if src not in _SCALE or dst not in _SCALE or _FAMILY[src] != _FAMILY[dst]:
        raise ValueError("incompatible_or_unknown_unit")
    scale_a, offset_a = _SCALE[src]
    scale_b, offset_b = _SCALE[dst]
    a=Decimal(scale_a.numerator)/Decimal(scale_a.denominator)
    b=Decimal(offset_a.numerator)/Decimal(offset_a.denominator)
    c=Decimal(scale_b.numerator)/Decimal(scale_b.denominator)
    d=Decimal(offset_b.numerator)/Decimal(offset_b.denominator)
    return (value*a+b-d)/c


def _calibrate(p):
    try:
        if p["correction_state"] != "RAW": return bad("already_corrected")
        gain = D(p["gain"])
        if gain <= 0: return bad("invalid_gain")
        with localcontext() as ctx:
            ctx.prec=80
            result = gain * D(p["raw_value"]) + D(p["offset"]) + D(p["temp_coefficient"]) * (D(p["ambient_temperature_c"]) - D(p["reference_temperature_c"]))
            return {"valid": True, "corrected_value": Q(result, p["rounding_places"])}
    except (KeyError, ValueError, TypeError, InvalidOperation): return bad("invalid_parameters")


def _certificate(p):
    try:
        c, m = p["certificate"], p["measurement"]
        if not isinstance(c, dict) or not isinstance(m, dict):
            return {"valid": False, "reasons": ["invalid_structure"]}
        keys = ("serial_number", "measurand", "status", "valid_from", "valid_to", "range_min", "range_max", "uncertainty", "unit", "traceability_chain_status")
        reasons = ["missing_" + key for key in keys if key not in c]

        if "serial_number" in c and c["serial_number"] != m.get("serial_number"): reasons.append("serial_mismatch")
        if "measurand" in c and c["measurand"] != m.get("measurand"): reasons.append("measurand_mismatch")
        if "status" in c and c["status"] != "CURRENT": reasons.append("calibration_not_current")

        def parse_date(source, key, absent_is_bad=False):
            if key not in source:
                return None, absent_is_bad
            value = source[key]
            if not isinstance(value, str) or len(value) != 10:
                return None, True
            try:
                parsed = date.fromisoformat(value)
            except ValueError:
                return None, True
            return (parsed, False) if parsed.isoformat() == value else (None, True)

        observed, bad_observed = parse_date(m, "date", True)
        left, bad_left = parse_date(c, "valid_from")
        right, bad_right = parse_date(c, "valid_to")
        if left is not None and right is not None:
            if left > right: reasons.append("invalid_validity_interval")
            elif observed is not None and not left <= observed <= right: reasons.append("outside_validity_dates")
        if bad_observed or bad_left or bad_right: reasons.append("invalid_date")

        low = high = reading = None
        bad_range_value = False
        if "range_min" in c:
            try: low = D(c["range_min"])
            except (ValueError, TypeError, InvalidOperation): bad_range_value = True
        if "range_max" in c:
            try: high = D(c["range_max"])
            except (ValueError, TypeError, InvalidOperation): bad_range_value = True
        try: reading = D(m["value"])
        except (KeyError, ValueError, TypeError, InvalidOperation): bad_range_value = True
        if low is not None and high is not None:
            if low > high: reasons.append("invalid_range")
            elif reading is not None and not low <= reading <= high: reasons.append("outside_calibration_range")
        if bad_range_value: reasons.append("invalid_range_or_value")

        if "uncertainty" in c:
            try:
                if D(c["uncertainty"]) < 0: reasons.append("invalid_uncertainty")
            except (ValueError, TypeError, InvalidOperation): reasons.append("missing_or_invalid_uncertainty")
        if "unit" in c and c["unit"] != m.get("unit"): reasons.append("unit_mismatch")
        if "traceability_chain_status" in c and c["traceability_chain_status"] != "DOCUMENTED": reasons.append("traceability_not_documented")
        return {"valid": not reasons, "reasons": reasons}
    except (KeyError, TypeError): return {"valid": False, "reasons": ["invalid_structure"]}


def _det(m):
    n = len(m)
    total = Decimal(0)
    for order in permutations(range(n)):
        inversions = sum(order[i] > order[j] for i in range(n) for j in range(i+1, n))
        term = Decimal(-1 if inversions % 2 else 1)
        for i, j in enumerate(order): term *= m[i][j]
        total += term
    return total


def _uncertainty(p):
    try:
        with localcontext() as ctx:
            ctx.prec = 40
            comp = p["components"]
            n = len(comp)
            if n < 1 or n > 3: return bad("unsupported_component_count")
            u, c = [], []
            for item in comp:
                c.append(D(item["sensitivity"]))
                if item["kind"] == "type_a":
                    xs = [D(x) for x in item["observations"]]
                    count = len(xs)
                    if count < 2: return bad("type_a_requires_two_observations")
                    average = sum(xs, Decimal(0)) / count
                    sample_var = sum(((x-average)*(x-average) for x in xs), Decimal(0)) / (count-1)
                    u.append((sample_var / count).sqrt())
                elif item["kind"] == "type_b_rectangular":
                    width = D(item["half_width"])
                    if width < 0: return bad("negative_half_width")
                    u.append(width / Decimal(3).sqrt())
                else: return bad("invalid_component_kind")
            if "correlation_matrix" in p:
                corr = [[D(v) for v in row] for row in p["correlation_matrix"]]
                if len(corr) != n or any(len(row) != n for row in corr): return bad("invalid_correlation_shape")
                for i in range(n):
                    if corr[i][i] != 1: return bad("invalid_correlation_diagonal")
                    for j in range(n):
                        if abs(corr[i][j]) > 1 or corr[i][j] != corr[j][i]: return bad("invalid_correlation_matrix")
                # Every principal minor must be nonnegative for a symmetric PSD matrix.
                for r in range(1, n+1):
                    for ix in combinations(range(n), r):
                        if _det([[corr[a][b] for b in ix] for a in ix]) < Decimal("-1e-24"):
                            return bad("non_psd_correlation_matrix")
            else: corr = [[Decimal(int(i == j)) for j in range(n)] for i in range(n)]
            variance = sum((c[i]*u[i])**2 for i in range(n))
            for i in range(n):
                for j in range(i+1, n): variance += 2*c[i]*c[j]*corr[i][j]*u[i]*u[j]
            if variance < Decimal("-1e-24"): return bad("negative_propagated_variance")
            combined = max(variance, Decimal(0)).sqrt()
            factor = D(p["coverage_factor"])
            if factor <= 0: return bad("invalid_coverage_factor")
            return {"valid": True, "standard_uncertainties": [F(x) for x in u], "combined_standard_uncertainty": F(combined), "expanded_uncertainty": F(factor*combined)}
    except (KeyError, ValueError, TypeError, InvalidOperation, ArithmeticError): return bad("invalid_parameters")


def _decision(p):
    try:
        center, radius, left, right = [D(p[k]) for k in ("y", "expanded_uncertainty", "lower_limit", "upper_limit")]
        if radius < 0: return bad("negative_uncertainty")
        if left > right: return bad("malformed_limits")
        with localcontext() as ctx:
            ctx.prec=80
            low, high = center-radius, center+radius
            if low >= left and high <= right: label = "ACCEPT"
            elif high < left or low > right: label = "REJECT"
            else: label = "INDETERMINATE"
            return {"valid": True, "lower": F(low), "upper": F(high), "decision": label}
    except (KeyError, ValueError, TypeError, InvalidOperation): return bad("invalid_parameters")


def _temporal(p):
    try:
        ts, now, age, skew, seq = [p[k] for k in ("timestamp_ms", "now_ms", "max_age_ms", "allowed_future_skew_ms", "sequence")]
        if any(isinstance(x, bool) or not isinstance(x, int) for x in (ts, now, age, skew, seq)) or age < 0 or skew < 0 or ts < 0 or now < 0 or not 0 <= seq <= 0xffffffff:
            return {"valid": False, "reason": "invalid_timestamp_or_parameters"}
        if ts - now > skew: return {"valid": False, "reason": "future_timestamp"}
        if now - ts > age: return {"valid": False, "reason": "stale_timestamp"}
        if p.get("last_sequence") is None: return {"valid": True, "reason": "first_sequence", "sequence_order": "FIRST"}
        last = p["last_sequence"]
        if isinstance(last, bool) or not isinstance(last, int) or not 0 <= last <= 0xffffffff: return {"valid": False, "reason": "invalid_last_sequence"}
        step = (seq - last) & 0xffffffff
        if step == 0: return {"valid": False, "reason": "duplicate_sequence"}
        if step == 0x80000000: return {"valid": False, "reason": "ambiguous_half_range"}
        if step > 0x80000000: return {"valid": False, "reason": "out_of_order_sequence"}
        return {"valid": True, "reason": "ok", "sequence_order": "NEWER"}
    except (KeyError, TypeError): return {"valid": False, "reason": "invalid_structure"}


def _end_to_end(p):
    out = {"valid": False, "decoded_measurement": None, "physical_quantity": None, "corrected_measurement": None,
           "temporal_validity": {"valid": False, "reason": "invalid_structure"},
           "calibration_validity": {"valid": False, "reasons": []}, "standard_uncertainty": None, "expanded_uncertainty": None,
           "conformity_decision": "INDETERMINATE", "error_reasons": []}
    try:
        with localcontext() as ctx:
            ctx.prec = 40
            decoded = _decode(p["sensor"])
            temporal = _temporal(p.get("temporal", {}))
            out["temporal_validity"] = temporal
            if not decoded["valid"]: out["error_reasons"].append("decode:" + decoded["reason"])
            if not temporal["valid"]: out["error_reasons"].append("temporal:" + temporal["reason"])
            if not decoded["valid"]: return out
            out["decoded_measurement"] = {
                "raw_count": decoded["raw_count"], "value": decoded["value"],
                "unit": p["units"]["from_unit"],
            }
            try:
                # Independent conversion path: sensor scaling is in from_unit,
                # then the value is converted once to the final to_unit.
                converted = _convert_value(D(decoded["value"]), p["units"]["from_unit"], p["units"]["to_unit"])
            except ValueError:
                out["error_reasons"].append("units:incompatible_or_unknown_unit")
                return out
            out["physical_quantity"] = {"value": F(converted), "unit": p["units"]["to_unit"]}

            calibration = dict(p["calibration"])
            # Calibration is expressed in to_unit: dimensionless gain, output-unit
            # offset, and output-unit-per-Celsius coefficient/temperature interval.
            calibration["raw_value"] = F(converted)
            corrected_result = _calibrate(calibration)
            corrected = None
            if not corrected_result["valid"]:
                out["error_reasons"].append("calibration:" + corrected_result["reason"])
            else:
                corrected = D(corrected_result["corrected_value"])
                out["corrected_measurement"] = {"value": F(corrected), "unit": p["units"]["to_unit"]}

            # The supplied uncertainty budget is already post-calibration in to_unit.
            # It is propagated as given and is not rescaled by calibration gain.
            unc = _uncertainty(p["uncertainty"])
            if not unc["valid"]:
                out["error_reasons"].append("uncertainty:" + unc["reason"])
            else:
                out["standard_uncertainty"] = unc["combined_standard_uncertainty"]
                out["expanded_uncertainty"] = unc["expanded_uncertainty"]

            if corrected is not None:
                cert = _certificate({"certificate": p["certificate"], "measurement": {
                    "serial_number": p["instrument_serial"], "measurand": p["measurand"], "date": p["measurement_date"],
                    "value": F(corrected), "unit": p["units"]["to_unit"]}})
                out["calibration_validity"] = cert
                if not cert["valid"]: out["error_reasons"].extend("certificate:" + reason for reason in cert["reasons"])
            if out["error_reasons"]: return out

            # Specification endpoints and expanded uncertainty are in to_unit.
            decision = _decision({"y": F(corrected), "expanded_uncertainty": unc["expanded_uncertainty"], **p["specification"]})
            if not decision["valid"]:
                out["error_reasons"].append("conformity:" + decision["reason"])
                return out
            out["conformity_decision"] = decision["decision"]
            out["conformity_interval"] = {"lower": decision["lower"], "upper": decision["upper"]}
            out["valid"] = True
            return out
    except (KeyError, TypeError, ValueError, ArithmeticError):
        out["error_reasons"].append("pipeline:invalid_input")
        return out


SOLVERS = {"S01": _decode, "S02": _convert, "S03": _calibrate, "S04": _certificate, "S05": _uncertainty, "S06": _decision, "S07": _temporal, "S08": _end_to_end}
