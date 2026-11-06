"""S08 — End-to-End Measurement Integrity.

Fixed processing order:
  (1) decode register frame + scale into units.from_unit (sensor rounding)
  (2) convert from_unit -> to_unit (S02 affine rules, not rounded)
  (3) calibrate: corrected = gain*physical + offset + tc*(Tamb - Tref)
      (Celsius temperature interval), rounded by calibration.rounding_places
  (4) uncertainty budget already in to_unit; no gain/unit-conversion scaling
  (5) S04 certificate evidence on corrected value / to_unit / serial / measurand / date
  (6) S06 conformity on [corrected - U, corrected + U] vs spec limits (inclusive)

Any failed stage -> valid=False, conformity_decision=INDETERMINATE.
Conformity interval is emitted only when every stage is valid.
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP, getcontext

getcontext().prec = 50

_TEMP = frozenset(("C", "F", "K"))
_PRESSURE = frozenset(("Pa", "kPa", "bar"))
_VOLTAGE = frozenset(("V", "mV"))

_UNIT_CATEGORY = {}
for _u in _TEMP:
    _UNIT_CATEGORY[_u] = "temp"
for _u in _PRESSURE:
    _UNIT_CATEGORY[_u] = "pressure"
for _u in _VOLTAGE:
    _UNIT_CATEGORY[_u] = "voltage"


def _num(value):
    """Convert a numeric string/int to Decimal. Raises on invalid input."""
    return Decimal(str(value))


def _fmt(d):
    """Format a Decimal without exponent notation."""
    if d is None:
        return None
    if d == 0:
        return "0"
    return format(d, "f")


def _quantize(value, places):
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _convert_unit(value, from_unit, to_unit):
    """Explicit affine conversion between units of one category."""
    if from_unit not in _UNIT_CATEGORY or to_unit not in _UNIT_CATEGORY:
        raise ValueError("unsupported unit")
    if _UNIT_CATEGORY[from_unit] != _UNIT_CATEGORY[to_unit]:
        raise ValueError("unsupported conversion across unit categories")
    if from_unit == to_unit:
        return value

    def to_base(v, u):
        if u == "C":
            return v
        if u == "F":
            return (v - Decimal(32)) * Decimal(5) / Decimal(9)
        if u == "K":
            return v - Decimal("273.15")
        if u == "Pa":
            return v
        if u == "kPa":
            return v * Decimal(1000)
        if u == "bar":
            return v * Decimal(100000)
        if u == "V":
            return v
        if u == "mV":
            return v / Decimal(1000)
        raise ValueError("unknown unit")

    def from_base(v, u):
        if u == "C":
            return v
        if u == "F":
            return v * Decimal(9) / Decimal(5) + Decimal(32)
        if u == "K":
            return v + Decimal("273.15")
        if u == "Pa":
            return v
        if u == "kPa":
            return v / Decimal(1000)
        if u == "bar":
            return v / Decimal(100000)
        if u == "V":
            return v
        if u == "mV":
            return v * Decimal(1000)
        raise ValueError("unknown unit")

    return from_base(to_base(value, from_unit), to_unit)


def _parse_frame(sensor):
    frame = str(sensor["frame_hex"]).strip()
    if frame.startswith(("0x", "0X")):
        frame = frame[2:]
    raw_bytes = bytes.fromhex(frame)
    width = int(sensor["width_bits"])
    if width not in (8, 16, 24, 32):
        raise ValueError("invalid width_bits")
    nbytes = width // 8
    if len(raw_bytes) > nbytes:
        raise ValueError("frame_hex too wide for width_bits")
    raw_bytes = raw_bytes.rjust(nbytes, b"\x00")
    byte_order = sensor["byte_order"]
    if byte_order not in ("big", "little"):
        raise ValueError("invalid byte_order")
    raw = int.from_bytes(raw_bytes, byte_order)
    if sensor.get("signed", False) and raw >= (1 << (width - 1)):
        raw -= 1 << width
    return raw


def solve(payload: dict) -> dict:
    errors = []

    # ------------------------------------------------------------------ stage 1: decode
    decode_ok = True
    decoded = None
    decoded_value = None
    from_unit = None
    try:
        sensor = payload["sensor"]
        units = payload["units"]
        raw = _parse_frame(sensor)
        for sentinel in sensor.get("sentinel_codes", []):
            if raw == int(sentinel):
                raise ValueError("raw count matches a sentinel code")
        scale = _num(sensor["scale"])
        places = int(sensor["rounding_places"])
        value = Decimal(raw) * scale
        if value == 0:
            value = Decimal(0)
        value = _quantize(value, places)
        from_unit = str(units["from_unit"])
        decoded_value = value
        decoded = {
            "raw_count": int(raw),
            "value": format(value, "f"),
            "unit": from_unit,
        }
    except Exception as exc:  # invalid input: preserve error, keep going
        decode_ok = False
        errors.append("decode_error: %s" % exc)

    # ------------------------------------------------------------------ stage 2: temporal (independent)
    temporal_ok = True
    temporal_reason = "ok"
    sequence_order = "NEWER"
    try:
        t = payload["temporal"]
        now_ms = int(t["now_ms"])
        timestamp_ms = int(t["timestamp_ms"])
        max_age_ms = int(t["max_age_ms"])
        allowed_future_skew_ms = int(t["allowed_future_skew_ms"])
        sequence = int(t["sequence"])
        last_sequence = t.get("last_sequence")
        last_sequence = None if last_sequence is None else int(last_sequence)
        reasons = []
        if timestamp_ms > now_ms + allowed_future_skew_ms:
            temporal_ok = False
            reasons.append("future_skew_exceeded")
        if now_ms - timestamp_ms > max_age_ms:
            temporal_ok = False
            reasons.append("max_age_exceeded")
        if last_sequence is not None and sequence <= last_sequence:
            temporal_ok = False
            reasons.append("sequence_not_newer")
        if temporal_ok:
            temporal_reason = "ok"
        else:
            temporal_reason = reasons[0]
            errors.append("temporal_error: %s" % reasons[0])
        if last_sequence is None:
            sequence_order = "FIRST"
        elif sequence > last_sequence:
            sequence_order = "NEWER"
        else:
            sequence_order = "FIRST"
    except Exception as exc:
        temporal_ok = False
        temporal_reason = "temporal_error: %s" % exc
        sequence_order = "FIRST"
        errors.append("temporal_error: %s" % exc)
    temporal_validity = {
        "valid": temporal_ok,
        "reason": temporal_reason,
        "sequence_order": sequence_order,
    }

    # ------------------------------------------------------------------ stage 3: units conversion
    units_ok = True
    physical_quantity = None
    physical_value = None
    to_unit = None
    try:
        to_unit = str(payload["units"]["to_unit"])
        if decoded is None:
            raise ValueError("missing decoded measurement")
        physical_value = _convert_unit(decoded_value, from_unit, to_unit)
        physical_quantity = {"value": _fmt(physical_value), "unit": to_unit}
    except Exception as exc:
        units_ok = False
        errors.append("units_error: %s" % exc)

    # ------------------------------------------------------------------ stage 4: calibration
    calibration_ok = True
    calibration_reasons = []
    corrected_measurement = None
    corrected_value = None
    try:
        cal = payload["calibration"]
        if str(cal["correction_state"]) != "RAW":
            calibration_ok = False
            calibration_reasons.append("correction_state_not_raw")
        if physical_value is None:
            calibration_ok = False
            calibration_reasons.append("missing_physical_quantity")
        if not calibration_ok:
            raise ValueError("; ".join(calibration_reasons))
        gain = _num(cal["gain"])
        offset = _num(cal["offset"])
        temp_coefficient = _num(cal["temp_coefficient"])
        ambient = _num(cal["ambient_temperature_c"])
        reference = _num(cal["reference_temperature_c"])
        cal_places = int(cal["rounding_places"])
        corrected = (
            gain * physical_value
            + offset
            + temp_coefficient * (ambient - reference)
        )
        corrected = _quantize(corrected, cal_places)
        corrected_value = corrected
        corrected_measurement = {
            "value": format(corrected.normalize(), "f"),
            "unit": to_unit,
        }
    except Exception as exc:
        calibration_ok = False
        if not calibration_reasons:
            calibration_reasons = ["calibration_error: %s" % exc]
        errors.append("calibration_error: %s" % exc)
    calibration_validity = {
        "valid": calibration_ok,
        "reasons": calibration_reasons,
    }

    # ------------------------------------------------------------------ stage 5: uncertainty (independent of calibration)
    uncertainty_ok = True
    standard_uncertainty = None
    expanded_uncertainty = None
    u_c = None
    try:
        u = payload["uncertainty"]
        components = u["components"]
        if not isinstance(components, list) or len(components) < 1:
            raise ValueError("components required")
        cover = _num(u["coverage_factor"])
        sensitivities = []
        for comp in components:
            kind = comp["kind"]
            sensitivity = _num(comp["sensitivity"])
            if kind == "type_a":
                observations = [_num(x) for x in comp["observations"]]
                n = len(observations)
                if n < 2:
                    raise ValueError("type_a needs at least 2 observations")
                mean = sum(observations) / Decimal(n)
                variance = sum((x - mean) ** 2 for x in observations) / Decimal(n - 1)
                component_u = sensitivity * variance.sqrt() / Decimal(n).sqrt()
            elif kind == "type_b_rectangular":
                half_width = _num(comp["half_width"])
                component_u = sensitivity * half_width / Decimal(3).sqrt()
            else:
                raise ValueError("unknown uncertainty kind %r" % kind)
            sensitivities.append(component_u)
        n = len(sensitivities)
        rho = [[Decimal(0)] * n for _ in range(n)]
        for i in range(n):
            rho[i][i] = Decimal(1)
        if "correlation_matrix" in u and u["correlation_matrix"] is not None:
            matrix = u["correlation_matrix"]
            if len(matrix) != n or any(len(row) != n for row in matrix):
                raise ValueError("correlation_matrix must be n x n")
            for i in range(n):
                for j in range(n):
                    rho[i][j] = _num(matrix[i][j])
        variance = Decimal(0)
        for i in range(n):
            for j in range(n):
                variance += rho[i][j] * sensitivities[i] * sensitivities[j]
        u_c = variance.sqrt()
        standard_uncertainty = _fmt(u_c)
        expanded_uncertainty = _fmt(cover * u_c)
    except Exception as exc:
        uncertainty_ok = False
        errors.append("uncertainty_error: %s" % exc)

    # ------------------------------------------------------------------ stage 6: certificate evidence
    certificate_ok = True
    certificate_reasons = []
    try:
        cert = payload["certificate"]
        if str(cert.get("serial_number", None)) != str(payload.get("instrument_serial", None)):
            certificate_ok = False
            certificate_reasons.append("serial_mismatch")
        if str(cert.get("measurand", None)) != str(payload.get("measurand", None)):
            certificate_ok = False
            certificate_reasons.append("measurand_mismatch")
        if str(cert.get("status", None)) != "CURRENT":
            certificate_ok = False
            certificate_reasons.append("certificate_not_current")
        measurement_date = date.fromisoformat(str(payload["measurement_date"]))
        valid_from = date.fromisoformat(str(cert["valid_from"]))
        valid_to = date.fromisoformat(str(cert["valid_to"]))
        if not (valid_from <= measurement_date <= valid_to):
            certificate_ok = False
            certificate_reasons.append("certificate_outside_validity_period")
        if str(cert.get("unit", None)) != to_unit:
            certificate_ok = False
            certificate_reasons.append("certificate_unit_mismatch")
        if corrected_value is None:
            certificate_ok = False
            certificate_reasons.append("range_applicability_unavailable")
        else:
            range_min = _num(cert["range_min"])
            range_max = _num(cert["range_max"])
            if not (range_min <= corrected_value <= range_max):
                certificate_ok = False
                certificate_reasons.append("measurement_outside_certificate_range")
    except Exception as exc:
        certificate_ok = False
        if not certificate_reasons:
            certificate_reasons = ["certificate_error: %s" % exc]
        errors.append("certificate_error: %s" % (certificate_reasons[0] if certificate_reasons else exc))
    if certificate_reasons and not errors or False:
        pass
    # ensure a certificate entry exists in error_reasons when it failed
    if not certificate_ok and not any(
        e.startswith("certificate_error:") for e in errors
    ):
        errors.append("certificate_error: " + "; ".join(certificate_reasons))

    # ------------------------------------------------------------------ stage 7: conformity (S06)
    all_stages_valid = (
        decode_ok
        and temporal_ok
        and units_ok
        and calibration_ok
        and uncertainty_ok
        and certificate_ok
    )
    conformity_decision = "INDETERMINATE"
    conformity_interval = None
    if all_stages_valid:
        cv = corrected_value
        U = u_c
        lower_limit = _num(payload["specification"]["lower_limit"])
        upper_limit = _num(payload["specification"]["upper_limit"])
        low = cv - U
        high = cv + U
        if lower_limit <= low and high <= upper_limit:
            conformity_decision = "ACCEPT"
        elif high < lower_limit or low > upper_limit:
            conformity_decision = "REJECT"
        else:
            conformity_decision = "INDETERMINATE"
        conformity_interval = {
            "lower": _fmt(low),
            "upper": _fmt(high),
        }
    else:
        if corrected_value is None or u_c is None:
            errors.append("conformity_indeterminate: missing corrected value or uncertainty")

    result = {
        "valid": all_stages_valid,
        "decoded_measurement": decoded,
        "physical_quantity": physical_quantity,
        "corrected_measurement": corrected_measurement,
        "temporal_validity": temporal_validity,
        "calibration_validity": calibration_validity,
        "standard_uncertainty": standard_uncertainty,
        "expanded_uncertainty": expanded_uncertainty,
        "conformity_decision": conformity_decision,
        "error_reasons": errors,
    }
    if all_stages_valid:
        result["conformity_interval"] = conformity_interval
    return result
