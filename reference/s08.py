"""Reference end-to-end pipeline composed from the S01-S07 reference tasks."""
from decimal import Decimal, localcontext
from . import s01, s02, s03, s04, s05, s06, s07
from .common import dec, fmt

UNIT_GROUPS = s02.UNITS


def _convert(value: Decimal, source: str, target: str) -> Decimal:
    group = next((g for g in UNIT_GROUPS.values() if source in g and target in g), None)
    if group is None:
        raise ValueError("incompatible_or_unknown_unit")
    source_scale, source_offset = group[source]
    target_scale, target_offset = group[target]
    base = value * Decimal(source_scale.numerator) / Decimal(source_scale.denominator)
    base += Decimal(source_offset.numerator) / Decimal(source_offset.denominator)
    shifted = base - Decimal(target_offset.numerator) / Decimal(target_offset.denominator)
    return shifted * Decimal(target_scale.denominator) / Decimal(target_scale.numerator)


def solve(payload: dict) -> dict:
    result = {
        "valid": False,
        "decoded_measurement": None,
        "physical_quantity": None,
        "corrected_measurement": None,
        "temporal_validity": {"valid": False, "reason": "invalid_structure"},
        "calibration_validity": {"valid": False, "reasons": []},
        "standard_uncertainty": None,
        "expanded_uncertainty": None,
        "conformity_decision": "INDETERMINATE",
        "error_reasons": [],
    }
    try:
        with localcontext() as context:
            context.prec = 40
            raw = s01.solve(payload["sensor"])
            temporal = s07.solve(payload.get("temporal", {}))
            result["temporal_validity"] = temporal
            if not raw["valid"]:
                result["error_reasons"].append("decode:" + raw["reason"])
            if not temporal["valid"]:
                result["error_reasons"].append("temporal:" + temporal["reason"])
            if not raw["valid"]:
                return result

            units = payload["units"]
            result["decoded_measurement"] = {
                "raw_count": raw["raw_count"], "value": raw["value"],
                "unit": units["from_unit"],
            }
            try:
                # Decode/scale is already in from_unit; perform the single S02
                # transform to final to_unit before any calibration coefficient is applied.
                physical = _convert(dec(raw["value"]), units["from_unit"], units["to_unit"])
            except ValueError:
                result["error_reasons"].append("units:incompatible_or_unknown_unit")
                return result
            result["physical_quantity"] = {"value": fmt(physical), "unit": units["to_unit"]}

            calibration = dict(payload["calibration"])
            # gain is dimensionless; offset and temperature coefficient use to_unit.
            # The ambient-reference interval is formed in Celsius as specified.
            calibration["raw_value"] = fmt(physical)
            corrected_result = s03.solve(calibration)
            corrected = None
            if not corrected_result["valid"]:
                result["error_reasons"].append("calibration:" + corrected_result["reason"])
            else:
                corrected = dec(corrected_result["corrected_value"])
                result["corrected_measurement"] = {"value": fmt(corrected), "unit": units["to_unit"]}

            # S08 uncertainty inputs are already post-calibration and in to_unit;
            # do not apply gain or the input-to-output unit conversion again.
            uncertainty = s05.solve(payload["uncertainty"])
            if not uncertainty["valid"]:
                result["error_reasons"].append("uncertainty:" + uncertainty["reason"])
            else:
                result["standard_uncertainty"] = uncertainty["combined_standard_uncertainty"]
                result["expanded_uncertainty"] = uncertainty["expanded_uncertainty"]

            if corrected is not None:
                evidence = s04.solve({"certificate": payload["certificate"], "measurement": {
                    "serial_number": payload["instrument_serial"],
                    "measurand": payload["measurand"],
                    "date": payload["measurement_date"],
                    "value": fmt(corrected),
                    "unit": units["to_unit"],
                }})
                result["calibration_validity"] = evidence
                if not evidence["valid"]:
                    result["error_reasons"].extend("certificate:" + reason for reason in evidence["reasons"])

            # Independent checks above are retained; no disposition is issued if any stage failed.
            if result["error_reasons"]:
                return result
            decision = s06.solve({
                # Result, expanded uncertainty and both specification limits share to_unit.
                "y": fmt(corrected),
                "expanded_uncertainty": uncertainty["expanded_uncertainty"],
                "lower_limit": payload["specification"]["lower_limit"],
                "upper_limit": payload["specification"]["upper_limit"],
            })
            if not decision["valid"]:
                result["error_reasons"].append("conformity:" + decision["reason"])
                return result
            result["conformity_decision"] = decision["decision"]
            result["conformity_interval"] = {"lower": decision["lower"], "upper": decision["upper"]}
            result["valid"] = True
            return result
    except (KeyError, TypeError, ValueError, ArithmeticError):
        result["error_reasons"].append("pipeline:invalid_input")
        return result
