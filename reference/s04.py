"""Known-correct synthetic calibration evidence applicability check."""
from datetime import date
from .common import dec

CERTIFICATE_FIELDS = (
    "serial_number", "measurand", "status", "valid_from", "valid_to",
    "range_min", "range_max", "uncertainty", "unit", "traceability_chain_status",
)


def _canonical_date(value):
    if not isinstance(value, str) or len(value) != 10:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def solve(payload: dict) -> dict:
    try:
        certificate, measurement = payload["certificate"], payload["measurement"]
        if not isinstance(certificate, dict) or not isinstance(measurement, dict):
            return {"valid": False, "reasons": ["invalid_structure"]}

        reasons = ["missing_" + key for key in CERTIFICATE_FIELDS if key not in certificate]

        # Check only comparisons for which the certificate side is available.
        if "serial_number" in certificate and certificate["serial_number"] != measurement.get("serial_number"):
            reasons.append("serial_mismatch")
        if "measurand" in certificate and certificate["measurand"] != measurement.get("measurand"):
            reasons.append("measurand_mismatch")
        if "status" in certificate and certificate["status"] != "CURRENT":
            reasons.append("calibration_not_current")

        date_fields = ((measurement, "date"), (certificate, "valid_from"), (certificate, "valid_to"))
        parsed_dates = []
        malformed_date = False
        for index, (source, key) in enumerate(date_fields):
            if key not in source:
                if index == 0:  # a missing measurement date is independently malformed
                    malformed_date = True
                parsed_dates.append(None)
            else:
                parsed = _canonical_date(source[key])
                malformed_date = malformed_date or parsed is None
                parsed_dates.append(parsed)
        observed, start, end = parsed_dates
        if start is not None and end is not None:
            if start > end:
                reasons.append("invalid_validity_interval")
            elif observed is not None and not start <= observed <= end:
                reasons.append("outside_validity_dates")
        if malformed_date:
            reasons.append("invalid_date")

        low = high = value = None
        range_parse_error = False
        if "range_min" in certificate:
            try:
                low = dec(certificate["range_min"])
            except (ValueError, TypeError):
                range_parse_error = True
        if "range_max" in certificate:
            try:
                high = dec(certificate["range_max"])
            except (ValueError, TypeError):
                range_parse_error = True
        try:
            if "value" not in measurement:
                raise ValueError("missing value")
            value = dec(measurement["value"])
        except (ValueError, TypeError):
            range_parse_error = True

        if low is not None and high is not None:
            if low > high:
                reasons.append("invalid_range")
            elif value is not None and not low <= value <= high:
                reasons.append("outside_calibration_range")
        if range_parse_error:
            reasons.append("invalid_range_or_value")

        if "uncertainty" in certificate:
            try:
                if dec(certificate["uncertainty"]) < 0:
                    reasons.append("invalid_uncertainty")
            except (ValueError, TypeError):
                reasons.append("missing_or_invalid_uncertainty")
        if "unit" in certificate and certificate["unit"] != measurement.get("unit"):
            reasons.append("unit_mismatch")
        if "traceability_chain_status" in certificate and certificate["traceability_chain_status"] != "DOCUMENTED":
            reasons.append("traceability_not_documented")

        return {"valid": not reasons, "reasons": reasons}
    except (KeyError, TypeError):
        return {"valid": False, "reasons": ["invalid_structure"]}
