"""S08 — End-to-End Measurement Integrity.

Implements solve(payload) -> dict following the fixed processing order:
(1) decode, (2) temporal, (3) units conversion, (4) calibration,
(5) uncertainty, (6) certificate evidence, (7) conformity.

All numeric work is done with :mod:`decimal` at 60 digits of precision so the
task-specific absolute tolerances are met comfortably.
"""

from decimal import Decimal, ROUND_HALF_UP, localcontext

TEMP_UNITS = frozenset({"C", "F", "K"})
PRESSURE_UNITS = frozenset({"Pa", "kPa", "bar"})
ELECTRIC_UNITS = frozenset({"V", "mV"})

_K = Decimal("273.15")
_PRESSURE_TO_PA = {"Pa": Decimal(1), "kPa": Decimal(1000), "bar": Decimal(100000)}
_ELECTRIC_TO_V = {"V": Decimal(1), "mV": Decimal("0.001")}


def _to_decimal(x):
    """Coerce an int / numeric string to a finite Decimal."""
    if isinstance(x, bool):
        raise ValueError("boolean is not numeric")
    if isinstance(x, int):
        d = Decimal(x)
    elif isinstance(x, float):
        d = Decimal(repr(x))
    elif isinstance(x, str):
        d = Decimal(x.strip())
    else:
        raise ValueError("value is not numeric")
    if not d.is_finite():
        raise ValueError("value is not finite")
    return d


def _quantize(value, places):
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _fmt(d):
    """Format a Decimal without exponent notation (schema-compatible)."""
    s = str(d)
    if "e" in s or "E" in s:
        s = format(d, "f")
    return s


def _to_celsius(value, unit):
    if unit == "C":
        return value
    if unit == "F":
        return (value - Decimal(32)) * Decimal(5) / Decimal(9)
    if unit == "K":
        return value - _K
    raise ValueError(f"unknown temperature unit {unit!r}")


def _from_celsius(celsius, unit):
    if unit == "C":
        return celsius
    if unit == "F":
        return celsius * Decimal(9) / Decimal(5) + Decimal(32)
    if unit == "K":
        return celsius + _K
    raise ValueError(f"unknown temperature unit {unit!r}")


def convert_unit(value, from_unit, to_unit):
    """S02 explicit affine conversion within one unit group."""
    if from_unit == to_unit:
        return value
    if from_unit in TEMP_UNITS and to_unit in TEMP_UNITS:
        return _from_celsius(_to_celsius(value, from_unit), to_unit)
    if from_unit in PRESSURE_UNITS and to_unit in PRESSURE_UNITS:
        pa = value * _PRESSURE_TO_PA[from_unit]
        return pa / _PRESSURE_TO_PA[to_unit]
    if from_unit in ELECTRIC_UNITS and to_unit in ELECTRIC_UNITS:
        volts = value * _ELECTRIC_TO_V[from_unit]
        return volts / _ELECTRIC_TO_V[to_unit]
    raise ValueError(f"no defined conversion from {from_unit} to {to_unit}")


def _invalid_pipeline(message):
    return {
        "valid": False,
        "decoded_measurement": None,
        "physical_quantity": None,
        "corrected_measurement": None,
        "temporal_validity": {
            "valid": False,
            "reason": message,
            "sequence_order": "FIRST",
        },
        "calibration_validity": {"valid": False, "reasons": [message]},
        "standard_uncertainty": None,
        "expanded_uncertainty": None,
        "conformity_decision": "INDETERMINATE",
        "error_reasons": [message],
    }


def solve(payload: dict) -> dict:
    with localcontext() as ctx:
        ctx.prec = 60
        return _solve(payload)


def _solve(payload):
    decode_reasons = []
    temporal_reasons = []
    units_reasons = []
    cal_reasons = []
    unc_reasons = []
    cert_reasons = []
    conf_reasons = []

    decoded_decimal = None
    decoded_output = None
    physical_decimal = None
    corrected_decimal = None

    decode_ok = False
    units_ok = False
    cal_ok = False
    unc_ok = False
    cert_ok = False

    # --- required top-level inputs ---
    try:
        sensor = payload["sensor"]
        units = payload["units"]
        temporal = payload["temporal"]
        calibration = payload["calibration"]
        uncertainty = payload["uncertainty"]
        certificate = payload["certificate"]
        specification = payload["specification"]
        instrument_serial = payload["instrument_serial"]
        measurand = payload["measurand"]
        measurement_date = payload["measurement_date"]
        from_unit = units["from_unit"]
        to_unit = units["to_unit"]
    except Exception as exc:
        return _invalid_pipeline(f"missing required input: {exc}")

    # (1) decode the register frame, scaled into units.from_unit
    try:
        frame_hex = sensor["frame_hex"]
        width_bits = int(sensor["width_bits"])
        byte_order = sensor["byte_order"]
        signed = bool(sensor["signed"])
        scale = _to_decimal(sensor["scale"])
        rounding_places = int(sensor["rounding_places"])
        sentinel_codes = sensor.get("sentinel_codes") or []
        if not isinstance(frame_hex, str) or not frame_hex:
            raise ValueError("frame_hex must be a non-empty string")
        if any(c not in "0123456789abcdefABCDEF" for c in frame_hex):
            raise ValueError("frame_hex contains non-hexadecimal characters")
        if len(frame_hex) * 4 != width_bits:
            raise ValueError("frame_hex length does not match width_bits")
        raw_count = int.from_bytes(
            bytes.fromhex(frame_hex), byte_order, signed=signed
        )
        if raw_count in sentinel_codes:
            raise ValueError("raw count matches a sentinel code")
        value_decimal = _quantize(Decimal(raw_count) * scale, rounding_places)
        decoded_decimal = value_decimal
        decoded_output = {
            "raw_count": raw_count,
            "value": str(value_decimal),
            "unit": from_unit,
        }
        decode_ok = True
    except Exception as exc:
        decode_reasons.append(f"decode: {exc}")

    # temporal validity (independent of the decode stage)
    sequence_order = "FIRST"
    try:
        now_ms = int(temporal["now_ms"])
        timestamp_ms = int(temporal["timestamp_ms"])
        max_age_ms = int(temporal["max_age_ms"])
        allowed_future_skew_ms = int(temporal["allowed_future_skew_ms"])
        sequence = int(temporal["sequence"])
        last_sequence = temporal.get("last_sequence")
        age_ms = now_ms - timestamp_ms
        if age_ms > max_age_ms:
            temporal_reasons.append("measurement age exceeds max_age_ms")
        if age_ms < -allowed_future_skew_ms:
            temporal_reasons.append("timestamp exceeds allowed future skew")
        if last_sequence is not None:
            sequence_order = "NEWER"
            if sequence <= int(last_sequence):
                temporal_reasons.append(
                    "sequence is not newer than last_sequence"
                )
    except Exception as exc:
        temporal_reasons.append(f"temporal: {exc}")
    temporal_ok = not temporal_reasons
    temporal_validity = {
        "valid": temporal_ok,
        "reason": "; ".join(temporal_reasons) if temporal_reasons else "ok",
        "sequence_order": sequence_order,
    }

    # (2) convert decoded value from from_unit to to_unit (no rounding)
    try:
        if decoded_decimal is None:
            raise ValueError("decoded measurement unavailable")
        physical_decimal = convert_unit(decoded_decimal, from_unit, to_unit)
        units_ok = True
    except Exception as exc:
        units_reasons.append(f"units: {exc}")
    physical_quantity = (
        {"value": _fmt(physical_decimal.normalize()), "unit": to_unit}
        if physical_decimal is not None else None
    )

    # (3) calibrate once; round only by calibration.rounding_places
    try:
        if physical_decimal is None:
            raise ValueError("physical quantity unavailable")
        gain = _to_decimal(calibration["gain"])
        offset = _to_decimal(calibration["offset"])
        temp_coefficient = _to_decimal(calibration["temp_coefficient"])
        ambient_temperature_c = _to_decimal(
            calibration["ambient_temperature_c"]
        )
        reference_temperature_c = _to_decimal(
            calibration["reference_temperature_c"]
        )
        if calibration.get("correction_state") != "RAW":
            raise ValueError("correction_state must be RAW")
        temperature_interval_c = ambient_temperature_c - reference_temperature_c
        corrected_raw = (
            gain * physical_decimal
            + offset
            + temp_coefficient * temperature_interval_c
        )
        corrected_decimal = _quantize(
            corrected_raw, int(calibration["rounding_places"])
        )
        cal_ok = True
    except Exception as exc:
        cal_reasons.append(f"calibration: {exc}")
    corrected_measurement = (
        {"value": _fmt(corrected_decimal.normalize()), "unit": to_unit}
        if corrected_decimal is not None else None
    )
    calibration_validity = {"valid": cal_ok, "reasons": cal_reasons}

    # (4) uncertainty budget (already in to_unit; not scaled by gain/conversion)
    u_standard = None
    u_expanded = None
    try:
        components = uncertainty["components"]
        coverage_factor = _to_decimal(uncertainty["coverage_factor"])
        count = len(components)
        if count < 1:
            raise ValueError("uncertainty budget needs at least one component")
        component_uncertainties = []
        for component in components:
            sensitivity = _to_decimal(component["sensitivity"])
            kind = component.get("kind")
            if kind == "type_a":
                observations = [_to_decimal(o) for o in component["observations"]]
                observation_count = len(observations)
                if observation_count < 2:
                    raise ValueError(
                        "type_a component needs at least 2 observations"
                    )
                mean = sum(observations) / observation_count
                variance = (
                    sum((o - mean) ** 2 for o in observations)
                    / (observation_count - 1)
                )
                standard = (
                    variance.sqrt()
                    / Decimal(observation_count).sqrt()
                    * sensitivity
                )
                component_uncertainties.append(standard)
            elif kind == "type_b_rectangular":
                half_width = _to_decimal(component["half_width"])
                component_uncertainties.append(
                    half_width / Decimal(3).sqrt() * sensitivity
                )
            else:
                raise ValueError(
                    f"unknown uncertainty component kind {kind!r}"
                )
        correlation_matrix = uncertainty.get("correlation_matrix")
        if correlation_matrix is not None:
            if len(correlation_matrix) != count or any(
                len(row) != count for row in correlation_matrix
            ):
                raise ValueError(
                    "correlation matrix must be square with one entry per "
                    "component"
                )
        combined_variance = Decimal(0)
        for i in range(count):
            combined_variance += (
                component_uncertainties[i] * component_uncertainties[i]
            )
            for j in range(i + 1, count):
                rho = (
                    Decimal(1)
                    if correlation_matrix is None
                    else _to_decimal(correlation_matrix[i][j])
                )
                combined_variance += (
                    Decimal(2)
                    * rho
                    * component_uncertainties[i]
                    * component_uncertainties[j]
                )
        if combined_variance < 0:
            combined_variance = Decimal(0)
        combined_standard = combined_variance.sqrt()
        u_standard = combined_standard
        u_expanded = coverage_factor * combined_standard
        unc_ok = True
    except Exception as exc:
        unc_reasons.append(f"uncertainty: {exc}")
    standard_uncertainty = _fmt(u_standard) if u_standard is not None else None
    expanded_uncertainty = _fmt(u_expanded) if u_expanded is not None else None

    # (5) certificate evidence (range applicability needs the corrected value)
    try:
        if certificate.get("serial_number") != instrument_serial:
            cert_reasons.append(
                "certificate serial_number does not match instrument_serial"
            )
        if certificate.get("measurand") != measurand:
            cert_reasons.append(
                "certificate measurand does not match measurand"
            )
        if certificate.get("status") != "CURRENT":
            cert_reasons.append("certificate status is not CURRENT")
        valid_from = certificate.get("valid_from")
        valid_to = certificate.get("valid_to")
        if not (
            isinstance(measurement_date, str)
            and isinstance(valid_from, str)
            and isinstance(valid_to, str)
            and valid_from <= measurement_date <= valid_to
        ):
            cert_reasons.append(
                "measurement date is outside the certificate validity interval"
            )
        if certificate.get("unit") != to_unit:
            cert_reasons.append(
                "certificate unit does not match units.to_unit"
            )
        if corrected_decimal is not None:
            range_min = _to_decimal(certificate["range_min"])
            range_max = _to_decimal(certificate["range_max"])
            if not (range_min <= corrected_decimal <= range_max):
                cert_reasons.append(
                    "corrected value is outside the certificate range"
                )
        cert_ok = not cert_reasons
    except Exception as exc:
        cert_reasons.append(f"certificate: {exc}")
        cert_ok = False

    # (6) conformity with inclusive decision rule
    validity = (
        decode_ok
        and temporal_ok
        and units_ok
        and cal_ok
        and unc_ok
        and cert_ok
    )
    conformity_decision = "INDETERMINATE"
    conformity_interval = None
    if validity:
        try:
            if corrected_decimal is None or u_expanded is None:
                raise ValueError(
                    "corrected value and expanded uncertainty are required"
                )
            lower_limit = _to_decimal(specification["lower_limit"])
            upper_limit = _to_decimal(specification["upper_limit"])
            lower = corrected_decimal - u_expanded
            upper = corrected_decimal + u_expanded
            if lower >= lower_limit and upper <= upper_limit:
                conformity_decision = "ACCEPT"
            elif lower > upper_limit or upper < lower_limit:
                conformity_decision = "REJECT"
            else:
                conformity_decision = "INDETERMINATE"
            conformity_interval = {
                "lower": _fmt(lower),
                "upper": _fmt(upper),
            }
        except Exception as exc:
            validity = False
            conf_reasons.append(f"conformity: {exc}")

    error_reasons = (
        decode_reasons
        + temporal_reasons
        + units_reasons
        + cal_reasons
        + unc_reasons
        + cert_reasons
        + conf_reasons
    )

    result = {
        "valid": validity,
        "decoded_measurement": decoded_output,
        "physical_quantity": physical_quantity,
        "corrected_measurement": corrected_measurement,
        "temporal_validity": temporal_validity,
        "calibration_validity": calibration_validity,
        "standard_uncertainty": standard_uncertainty,
        "expanded_uncertainty": expanded_uncertainty,
        "conformity_decision": conformity_decision,
        "error_reasons": error_reasons,
    }
    if conformity_interval is not None:
        result["conformity_interval"] = conformity_interval
    return result
