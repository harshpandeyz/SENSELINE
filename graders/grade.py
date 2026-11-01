"""Deterministic contract grading with separate physical and execution metrics."""
from __future__ import annotations

import json
import math
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
TASK_DIRS = {p.name.split("_", 1)[0]: p for p in (ROOT / "tasks").iterdir() if p.is_dir()}
TOLERANCES = {
    "S01": {"value": Decimal(0)},
    "S02": {"value": Decimal(0)},
    "S03": {"corrected_value": Decimal(0)},
    "S04": {},
    "S05": {"standard_uncertainties": Decimal("1e-16"), "combined_standard_uncertainty": Decimal("1e-16"), "expanded_uncertainty": Decimal("1e-16")},
    "S06": {"lower": Decimal(0), "upper": Decimal(0)},
    "S07": {},
    "S08": {"decoded_measurement.value": Decimal(0), "physical_quantity.value": Decimal(0), "corrected_measurement.value": Decimal(0), "standard_uncertainty": Decimal("1e-16"), "expanded_uncertainty": Decimal("1e-16"), "conformity_interval.lower": Decimal("1e-16"), "conformity_interval.upper": Decimal("1e-16")},
}

# Grader-owned unit transforms, kept separate from both reference and oracle code.
# Each unit is mapped to a canonical unit as value*scale+offset.
UNIT_TRANSFORMS = {
    "C": ("temperature", Fraction(1), Fraction(0)),
    "F": ("temperature", Fraction(5, 9), Fraction(-160, 9)),
    "K": ("temperature", Fraction(1), Fraction(-27315, 100)),
    "Pa": ("pressure", Fraction(1), Fraction(0)),
    "kPa": ("pressure", Fraction(1000), Fraction(0)),
    "bar": ("pressure", Fraction(100000), Fraction(0)),
    "V": ("voltage", Fraction(1), Fraction(0)),
    "mV": ("voltage", Fraction(1, 1000), Fraction(0)),
}


def load_cases(task: str) -> list[dict]:
    path = ROOT / "graders" / "hidden" / f"{task}.json"
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def load_schema(task: str) -> dict:
    return json.loads((TASK_DIRS[task] / "output.schema.json").read_text(encoding="utf-8"))


def _schema_errors(instance: Any, schema: dict) -> list[str]:
    try:
        from jsonschema import Draft202012Validator
        return [e.message for e in Draft202012Validator(schema).iter_errors(instance)]
    except ImportError:
        # Only useful for minimal offline source inspection; the pinned install includes jsonschema.
        return ["jsonschema dependency is unavailable"]


def _json_safe(value: Any):
    if isinstance(value, Decimal):
        return {"__non_json_type__": "Decimal", "value": str(value)}
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return {"__non_json_type__": type(value).__name__, "repr": repr(value)}


def _tolerance(task: str, path: tuple[str, ...]) -> Decimal:
    dotted = ".".join(path)
    mapping = TOLERANCES[task]
    if task == "S05" and path and path[0] == "standard_uncertainties":
        return mapping["standard_uncertainties"]
    return mapping.get(dotted, mapping.get(path[-1], Decimal(0)) if path else Decimal(0))


def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def compare(task: str, expected: Any, actual: Any, path: tuple[str, ...] = ()) -> tuple[bool, list[Decimal]]:
    """Compare semantic content and numeric tolerances; schema compliance is graded separately."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(expected) != set(actual):
            return False, []
        ok, errors = True, []
        for key in expected:
            child_ok, child_errors = compare(task, expected[key], actual[key], path + (key,))
            ok = ok and child_ok
            errors.extend(child_errors)
        return ok, errors
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return False, []
        ok, errors = True, []
        for index, (left, right) in enumerate(zip(expected, actual)):
            child_ok, child_errors = compare(task, left, right, path + (str(index),))
            ok = ok and child_ok
            errors.extend(child_errors)
        return ok, errors
    if isinstance(expected, bool) or expected is None:
        return type(expected) is type(actual) and expected == actual, []
    expected_number = _decimal(expected)
    if expected_number is not None:
        actual_number = _decimal(actual)
        if actual_number is not None:
            error = abs(expected_number - actual_number)
            return error <= _tolerance(task, path), [error]
    return type(expected) is type(actual) and expected == actual, []


def _get_path(value: Any, path: tuple[str, ...]) -> Any:
    for part in path:
        if isinstance(value, list):
            try:
                value = value[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def _is_numeric_leaf(value: Any) -> bool:
    return _decimal(value) is not None


def _numeric_leaves(value: Any, path: tuple[str, ...] = ()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _numeric_leaves(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _numeric_leaves(child, path + (str(index),))
    elif _is_numeric_leaf(value):
        yield path, value


def _field_unit(task: str, payload: dict, path: tuple[str, ...]) -> str:
    dotted = ".".join(path)
    if task == "S01":
        return "scaled sensor count"
    if task == "S02":
        return str(payload.get("to_unit", "task-defined output unit"))
    if task == "S03":
        return "MU (task-defined measurand unit)"
    if task == "S05":
        return "MU (task-defined measurand unit)"
    if task == "S06":
        return "MU (task-defined specification unit)"
    if task == "S07":
        return "milliseconds" if "timestamp" in dotted or dotted.endswith("_ms") else "sequence count"
    if task == "S08":
        unit = str(payload.get("units", {}).get("to_unit", "task-defined output unit"))
        if dotted.endswith("raw_count"):
            return "register count"
        if dotted.endswith("decoded_measurement.value"):
            return str(payload.get("units", {}).get("from_unit", "sensor input unit"))
        return unit
    return "task-defined unit"


def _fraction_decimal(value: Fraction) -> Decimal:
    return Decimal(value.numerator) / Decimal(value.denominator)


def convert_unit_value(value: Decimal, source: str, target: str) -> Decimal | None:
    """Convert between task-supported units without using reference/oracle helpers."""
    # Preserve exact values for the identity transform.  The affine Fraction
    # route below is exact algebraically but Decimal division by 9 can leave a
    # one-ulp residue when converting a unit to itself (for example 78.9 F).
    if source == target and source in UNIT_TRANSFORMS:
        return value
    src, dst = UNIT_TRANSFORMS.get(source), UNIT_TRANSFORMS.get(target)
    if src is None or dst is None or src[0] != dst[0]:
        return None
    with localcontext() as context:
        context.prec = 80
        canonical = value * _fraction_decimal(src[1]) + _fraction_decimal(src[2])
        return (canonical - _fraction_decimal(dst[2])) / _fraction_decimal(dst[1])


def _unit_pair_path(task: str, path: tuple[str, ...]) -> tuple[str, ...] | None:
    if task == "S02" and path == ("value",):
        return ()
    if task == "S08" and path in (
        ("decoded_measurement", "value"),
        ("physical_quantity", "value"),
        ("corrected_measurement", "value"),
    ):
        return path[:-1]
    return None


def _unit_pairs(task: str, payload: dict, expected: Any) -> list[tuple[tuple[str, ...], dict]]:
    if not isinstance(expected, dict):
        return []
    if task == "S02" and expected.get("valid") is True:
        return [((), expected)]
    if task == "S08":
        pairs = []
        units = payload.get("units", {}) if isinstance(payload, dict) else {}
        for path, required_unit in (
            (("decoded_measurement",), units.get("from_unit")),
            (("physical_quantity",), units.get("to_unit")),
            (("corrected_measurement",), units.get("to_unit")),
        ):
            value = _get_path(expected, path)
            if isinstance(value, dict) and "value" in value and "unit" in value:
                contract_pair = dict(value)
                if isinstance(required_unit, str):
                    contract_pair["unit"] = required_unit
                pairs.append((path, contract_pair))
        return pairs
    return []


def _unit_pair_value(task: str, payload: dict, expected_pair: dict, actual_pair: Any, value_path: tuple[str, ...]) -> tuple[Decimal | None, dict]:
    expected_unit = expected_pair.get("unit")
    actual_unit = actual_pair.get("unit") if isinstance(actual_pair, dict) else None
    raw_actual = _decimal(actual_pair.get("value")) if isinstance(actual_pair, dict) else None
    converted = convert_unit_value(raw_actual, actual_unit, expected_unit) if raw_actual is not None and isinstance(actual_unit, str) and isinstance(expected_unit, str) else None
    # Keep numeric magnitude separate from unit-label correctness. If a unit
    # is missing or unsupported, grade the scalar independently; the unit and
    # physical-equivalence metrics still reject its physical interpretation.
    physical_comparison = converted
    comparison = converted if converted is not None else raw_actual
    # S02 requires an output rounded in the requested unit. An alternate but
    # physically equivalent unit pair is compared after that requested rounding.
    if task == "S02" and converted is not None and actual_unit != expected_unit:
        places = payload.get("rounding_places")
        if isinstance(places, int) and not isinstance(places, bool) and 0 <= places <= 12:
            with localcontext() as context:
                context.prec = 80
                comparison = converted.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)
                physical_comparison = comparison
    expected_value = _decimal(expected_pair.get("value"))
    tolerance = _tolerance(task, value_path)
    equivalent = expected_value is not None and physical_comparison is not None and abs(expected_value - physical_comparison) <= tolerance
    return comparison, {
        "expected_unit": expected_unit,
        "actual_unit": actual_unit,
        "unit_correct": isinstance(actual_unit, str) and actual_unit == expected_unit,
        "physically_equivalent": equivalent,
        "actual_in_expected_unit": str(converted) if converted is not None else None,
        "comparison_actual": str(comparison) if comparison is not None else None,
    }


def unit_diagnostics(task: str, payload: dict, expected: Any, actual: Any) -> list[dict]:
    diagnostics = []
    for pair_path, expected_pair in _unit_pairs(task, payload, expected):
        actual_pair = _get_path(actual, pair_path)
        value_path = pair_path + ("value",)
        _, info = _unit_pair_value(task, payload, expected_pair, actual_pair, value_path)
        diagnostics.append({"field": ".".join(pair_path) or "result", **info})
    return diagnostics


def numerical_diagnostics(task: str, payload: dict, expected: Any, actual: Any) -> list[dict]:
    diagnostics = []
    for path, expected_raw in _numeric_leaves(expected):
        actual_raw = _get_path(actual, path)
        expected_value = _decimal(expected_raw)
        actual_value = _decimal(actual_raw)
        unit_path = _unit_pair_path(task, path)
        actual_unit = None
        actual_in_expected_unit = None
        if unit_path is not None:
            expected_pair = _get_path(expected, unit_path)
            actual_pair = _get_path(actual, unit_path)
            if isinstance(expected_pair, dict):
                actual_value, pair_info = _unit_pair_value(task, payload, expected_pair, actual_pair, path)
                actual_unit = pair_info["actual_unit"]
                actual_in_expected_unit = pair_info["actual_in_expected_unit"]
        tolerance = _tolerance(task, path)
        if expected_value is None or actual_value is None:
            diagnostics.append({
                "field": ".".join(path), "unit": _field_unit(task, payload, path),
                "expected": str(expected_raw), "actual": _json_safe(actual_raw),
                "comparison_actual": str(actual_value) if actual_value is not None else None,
                "actual_unit": actual_unit,
                "actual_in_expected_unit": actual_in_expected_unit,
                "absolute_error": None, "relative_error": None,
                "permitted_tolerance": str(tolerance), "normalized_error": None,
                "within_tolerance": False,
            })
            continue
        absolute = abs(expected_value - actual_value)
        relative = absolute / abs(expected_value) if expected_value else None
        normalized = (absolute / tolerance) if tolerance else (Decimal(0) if absolute == 0 else None)
        diagnostics.append({
            "field": ".".join(path), "unit": _field_unit(task, payload, path),
            "expected": str(expected_value), "actual": str(actual_raw),
            "comparison_actual": str(actual_value),
            "actual_unit": actual_unit,
            "actual_in_expected_unit": actual_in_expected_unit,
            "absolute_error": str(absolute),
            "relative_error": str(relative) if relative is not None else None,
            "permitted_tolerance": str(tolerance),
            "normalized_error": str(normalized) if normalized is not None else "infinity",
            "within_tolerance": absolute <= tolerance,
        })
    return diagnostics


def _bool_paths(task: str, expected: Any) -> list[tuple[str, ...]]:
    possible = [("valid",)]
    if task == "S08":
        possible.extend([("calibration_validity", "valid"), ("temporal_validity", "valid")])
    return [path for path in possible if isinstance(_get_path(expected, path), bool)]


def _decision(expected: Any) -> Any:
    if not isinstance(expected, dict):
        return None
    return expected.get("conformity_decision", expected.get("decision"))


def _candidate_claims_valid(actual: Any) -> bool:
    if not isinstance(actual, dict):
        return False
    return actual.get("valid") is True or _decision(actual) == "ACCEPT"


def grade_module(task: str, module: Any, label: str = "candidate", on_case: Callable[[dict], None] | None = None) -> dict:
    """Grade a callable facade. Untrusted candidate facades must be DockerCandidate, never imported here."""
    rows = []
    schema = load_schema(task)
    for vector in load_cases(task):
        execution_error, candidate_stdout, candidate_stderr = None, "", ""
        try:
            actual = module.solve(vector["input"])
            candidate_stdout = getattr(module, "last_candidate_stdout", "")
            candidate_stderr = getattr(module, "last_candidate_stderr", "")
        except Exception as exc:
            if getattr(exc, "secure_unavailable", False):
                raise
            actual = None
            execution_error = f"{type(exc).__name__}: {exc}"
            candidate_stdout = getattr(exc, "candidate_stdout", "")
            candidate_stderr = getattr(exc, "candidate_stderr", "")
        safe_actual = _json_safe(actual)
        schema_errors = _schema_errors(actual, schema)
        semantic_correct, _ = compare(task, vector["expected"], actual)
        numeric = numerical_diagnostics(task, vector["input"], vector["expected"], actual)
        numeric_correct = all(item["within_tolerance"] for item in numeric)
        unit_rows = unit_diagnostics(task, vector["input"], vector["expected"], actual)
        unit_correct = all(item["unit_correct"] for item in unit_rows) if unit_rows else None
        physical_equivalence = all(item["physically_equivalent"] for item in unit_rows) if unit_rows else None
        physical_integrity_correct = numeric_correct and (physical_equivalence is not False)
        bool_paths = _bool_paths(task, vector["expected"])
        validity_correct = all(type(_get_path(actual, p)) is bool and _get_path(actual, p) == _get_path(vector["expected"], p) for p in bool_paths)
        decision_expected, decision_actual = _decision(vector["expected"]), _decision(actual)
        has_decision = decision_expected is not None
        decision_correct = (not has_decision) or decision_actual == decision_expected
        # A failed process is reported only as a runtime/execution failure. A
        # response is malformed when it exists but cannot be a task JSON object
        # (including the runtime's sentinel for a non-JSON Python return value).
        malformed_response = execution_error is None and (
            not isinstance(actual, dict) or "__non_json_candidate_output__" in actual
        )
        missing_unit_claimed_valid = any(item["actual_unit"] is None for item in unit_rows) and _candidate_claims_valid(actual)
        passed = not execution_error and not schema_errors and semantic_correct
        failure_dimensions = []
        if execution_error:
            failure_dimensions.append("execution")
        if malformed_response:
            failure_dimensions.append("malformed_response")
        if schema_errors:
            failure_dimensions.append("output_schema")
        if not numeric_correct:
            failure_dimensions.append("numerical_value")
        if unit_rows and not unit_correct:
            failure_dimensions.append("physical_unit")
        if unit_rows and not physical_equivalence:
            failure_dimensions.append("physical_quantity")
        if not validity_correct:
            failure_dimensions.append("validity_state")
        if has_decision and not decision_correct:
            failure_dimensions.append("engineering_decision")
        if missing_unit_claimed_valid:
            failure_dimensions.append("semantic_integrity")
        if not semantic_correct and numeric_correct and validity_correct and decision_correct:
            failure_dimensions.append("exact_semantic_contract")

        physical_value_wrong = not numeric_correct or any(
            item["actual_unit"] is not None and not item["physically_equivalent"]
            for item in unit_rows
        )
        validity_promoted_invalid = any(
            _get_path(vector["expected"], path) is False and _get_path(actual, path) is True
            for path in bool_paths
        )
        unsafe_decision = task in ("S06", "S08") and decision_expected != "ACCEPT" and decision_actual == "ACCEPT"
        claims_valid = _candidate_claims_valid(actual)
        silent_reasons = []
        if physical_value_wrong and claims_valid:
            silent_reasons.append("incorrect_physical_measurement_or_unit_claimed_valid")
        if validity_promoted_invalid:
            silent_reasons.append("invalid_measurement_or_calibration_marked_valid")
        if unsafe_decision:
            silent_reasons.append("nonacceptable_measurement_marked_accept")
        row = {
            "id": vector["id"], "category": vector["category"], "passed": passed,
            "schema_valid": not schema_errors, "schema_errors": schema_errors,
            "semantic_correct": semantic_correct, "numerical_correct": numeric_correct,
            "physical_unit_correct": unit_correct,
            "physical_equivalence_correct": physical_equivalence,
            "physical_integrity_correct": physical_integrity_correct,
            "semantic_integrity_failure": missing_unit_claimed_valid,
            "unit_diagnostics": unit_rows,
            "validity_state_correct": validity_correct,
            "engineering_decision_correct": decision_correct,
            "runtime_failure": execution_error is not None,
            "malformed_response": malformed_response, "error": execution_error,
            "failure_dimensions": failure_dimensions,
            "contract_violation": bool(schema_errors) or not semantic_correct,
            "silent_corruption": bool(silent_reasons), "silent_corruption_reasons": silent_reasons,
            "unsafe_acceptance": unsafe_decision,
            "expected_disposition": decision_expected, "actual_disposition": decision_actual,
            "expected": _json_safe(vector["expected"]), "actual": safe_actual,
            "numerical_diagnostics": numeric,
            "candidate_stdout": candidate_stdout, "candidate_stderr": candidate_stderr,
        }
        rows.append(row)
        if on_case:
            on_case(row)
    return {
        "task": task, "candidate": label, "case_count": len(rows),
        "passed": sum(row["passed"] for row in rows),
        "accuracy": sum(row["passed"] for row in rows) / len(rows), "cases": rows,
    }


def truth_decision(output):
    return _decision(output)


def calibration_valid(output, task):
    if not isinstance(output, dict):
        return False
    if task == "S04":
        return output.get("valid") is True
    value = output.get("calibration_validity")
    return isinstance(value, dict) and value.get("valid") is True


def _rate(numerator: int, denominator: int) -> dict:
    return {"numerator": int(numerator), "denominator": int(denominator), "value": numerator / denominator if denominator else None}


def _pass_metric(reports, all_pass):
    if not reports:
        return _rate(0, 0)
    distinct = {}
    for index, report in enumerate(reports):
        base = (report.get("model_id"), report.get("agent"), report.get("task"))
        repetition = report.get("trial", f"__record_{index}")
        distinct[base + (repetition,)] = report.get("task_accuracy", 0) == 1.0
    grouped = {}
    for key, passed in distinct.items():
        grouped.setdefault(key[:3], []).append(passed)
    numerator = denominator = 0
    for values in grouped.values():
        n, correct = len(values), sum(values)
        if n < 3:
            continue
        combinations = math.comb(n, 3)
        successes = math.comb(correct, 3) if all_pass and correct >= 3 else 0
        if not all_pass:
            failures = math.comb(n - correct, 3) if n - correct >= 3 else 0
            successes = combinations - failures
        numerator += successes
        denominator += combinations
    return _rate(numerator, denominator)


def _metric_groups(rows, flag):
    values = [flag(row) for row in rows]
    relevant = [value for value in values if value is not None]
    correct = sum(value is True for value in relevant)
    return _rate(correct, len(relevant))


def _numerical_groups(all_rows):
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for task, row in all_rows:
        for item in row["numerical_diagnostics"]:
            key = (task, item["field"], item["unit"])
            groups.setdefault(key, []).append(item)
    result = {}
    for (task, field, unit), values in sorted(groups.items()):
        parseable = [Decimal(item["absolute_error"]) for item in values if item["absolute_error"] is not None]
        normalized = [Decimal(item["normalized_error"]) for item in values if item["normalized_error"] not in (None, "infinity")]
        result[f"{task}.{field} [{unit}]"] = {
            "field": field, "task": task, "unit": unit,
            "case_count": len(values), "numeric_actual_count": len(parseable),
            "within_tolerance_count": sum(item["within_tolerance"] for item in values),
            "mean_absolute_error": str(sum(parseable, Decimal(0)) / len(parseable)) if parseable else None,
            "maximum_absolute_error": str(max(parseable)) if parseable else None,
            "maximum_normalized_error": str(max(normalized)) if normalized else ("infinity" if any(item["normalized_error"] == "infinity" for item in values) else None),
            "permitted_tolerance": values[0]["permitted_tolerance"],
        }
    return result


def _uncertainty_values_correct(task: str, row: dict) -> bool:
    diagnostics = row["numerical_diagnostics"]
    if task == "S05":
        selected = [item for item in diagnostics if item["field"].startswith("standard_uncertainties.") or item["field"] in ("combined_standard_uncertainty", "expanded_uncertainty")]
    else:
        selected = [item for item in diagnostics if item["field"] in ("standard_uncertainty", "expanded_uncertainty")]
    return bool(selected) and all(item["within_tolerance"] for item in selected)


def compute_metrics(task_reports: list[dict], trial_reports: list[dict] | None = None) -> dict:
    all_rows = [(report["task"], row) for report in task_reports for row in report["cases"]]
    total = len(all_rows)
    silent = sum(row["silent_corruption"] for _, row in all_rows)
    uar_rows = [(task, row) for task, row in all_rows if task in ("S06", "S08") and row["expected_disposition"] != "ACCEPT"]
    uar = sum(row["actual_disposition"] == "ACCEPT" for _, row in uar_rows)
    frr_rows = [(task, row) for task, row in all_rows if task in ("S06", "S08") and row["expected_disposition"] == "ACCEPT"]
    frr = sum(row["actual_disposition"] == "REJECT" for _, row in frr_rows)
    boundary_rows = [(task, row) for task, row in all_rows if task in ("S06", "S08") and row["category"] == "boundary"]
    calibration_rows = [(task, row) for task, row in all_rows if task in ("S04", "S08") and calibration_valid(row["expected"], task)]
    uncertainty_rows = []
    for task, row in all_rows:
        expected = row["expected"]
        if task == "S05" and isinstance(expected, dict) and expected.get("valid") is True:
            uncertainty_rows.append((task, row))
        elif task == "S08" and isinstance(expected, dict) and expected.get("standard_uncertainty") is not None:
            uncertainty_rows.append((task, row))

    per_task = {}
    for task in sorted({task for task, _ in all_rows}):
        rows = [row for code, row in all_rows if code == task]
        validity_rows = [row for row in rows if isinstance(row["expected"], dict) and isinstance(row["expected"].get("valid"), bool)]
        decision_rows = [row for row in rows if row["expected_disposition"] is not None]
        unsafe_rows = [row for row in rows if task in ("S06", "S08") and row["expected_disposition"] != "ACCEPT"]
        numeric_rows = [row for row in rows if row["numerical_diagnostics"]]
        per_task[task] = {
            "functional_correctness": _rate(sum(row["passed"] for row in rows), len(rows)),
            "schema_compliance": _rate(sum(row["schema_valid"] for row in rows), len(rows)),
            "numerical_correctness": _rate(sum(row["numerical_correct"] for row in numeric_rows), len(numeric_rows)),
            "physical_unit_correctness": _rate(
                sum(row["physical_unit_correct"] is True for row in rows if row["physical_unit_correct"] is not None),
                sum(row["physical_unit_correct"] is not None for row in rows),
            ),
            "physical_integrity_correctness": _rate(sum(row["physical_integrity_correct"] for row in rows), len(rows)),
            "semantic_integrity_failures": _rate(sum(row["semantic_integrity_failure"] for row in rows), len(rows)),
            "validity_state_correctness": _rate(sum(row["validity_state_correct"] for row in validity_rows), len(validity_rows)),
            "engineering_decision_correctness": _rate(sum(row["engineering_decision_correct"] for row in decision_rows), len(decision_rows)),
            "execution_failures": _rate(sum(row["runtime_failure"] for row in rows), len(rows)),
            "malformed_response_rate": _rate(sum(row["malformed_response"] for row in rows), len(rows)),
            "contract_violations": _rate(sum(row["contract_violation"] for row in rows), len(rows)),
            "silent_corruption_rate": _rate(sum(row["silent_corruption"] for row in rows), len(rows)),
            "unsafe_acceptance_rate": _rate(sum(row["actual_disposition"] == "ACCEPT" for row in unsafe_rows), len(unsafe_rows)),
        }

    task_accuracies = [item["functional_correctness"]["value"] for item in per_task.values() if item["functional_correctness"]["value"] is not None]
    e2e_rows = [row for task, row in all_rows if task == "S08"]
    uncertainty_correct = sum(_uncertainty_values_correct(task, row) for task, row in uncertainty_rows)
    all_unit_rows = [item for _, row in all_rows for item in row["unit_diagnostics"]]
    return {
        "case_count": total,
        "functional_correctness": _rate(sum(row["passed"] for _, row in all_rows), total),
        "schema_compliance": _rate(sum(row["schema_valid"] for _, row in all_rows), total),
        "numerical_correctness": _metric_groups([row for _, row in all_rows], lambda row: row["numerical_correct"] if row["numerical_diagnostics"] else None),
        "physical_unit_correctness": _rate(sum(item["unit_correct"] for item in all_unit_rows), len(all_unit_rows)),
        "physical_equivalence_correctness": _rate(sum(item["physically_equivalent"] for item in all_unit_rows), len(all_unit_rows)),
        "physical_integrity_correctness": _rate(sum(row["physical_integrity_correct"] for _, row in all_rows), total),
        "semantic_integrity_failures": _rate(sum(row["semantic_integrity_failure"] for _, row in all_rows), total),
        "validity_state_correctness": _metric_groups([row for _, row in all_rows], lambda row: row["validity_state_correct"] if isinstance(row["expected"], dict) and isinstance(row["expected"].get("valid"), bool) else None),
        "engineering_decision_correctness": _metric_groups([row for _, row in all_rows], lambda row: row["engineering_decision_correct"] if row["expected_disposition"] is not None else None),
        "execution_failures": _rate(sum(row["runtime_failure"] for _, row in all_rows), total),
        "malformed_response_rate": _rate(sum(row["malformed_response"] for _, row in all_rows), total),
        "contract_violations": _rate(sum(row["contract_violation"] for _, row in all_rows), total),
        "end_to_end_correctness": _rate(sum(row["passed"] for row in e2e_rows), len(e2e_rows)),
        "silent_corruption_rate": _rate(silent, total),
        "unsafe_acceptance_rate": _rate(uar, len(uar_rows)),
        "numerical_error_by_field_unit": _numerical_groups(all_rows),
        "calibration_validity_recall": _rate(sum(calibration_valid(row["actual"], task) for task, row in calibration_rows), len(calibration_rows)),
        "uncertainty_calculation_accuracy": _rate(uncertainty_correct, len(uncertainty_rows)),
        "false_rejection_rate": _rate(sum(row["actual_disposition"] == "REJECT" for _, row in frr_rows), len(frr_rows)),
        "boundary_decision_accuracy": _rate(sum(row["engineering_decision_correct"] for _, row in boundary_rows), len(boundary_rows)),
        "macro_average_task_accuracy": sum(task_accuracies) / len(task_accuracies) if task_accuracies else None,
        "per_task": per_task,
        "pass_at_3": _pass_metric(trial_reports, all_pass=False),
        "pass_cubed": _pass_metric(trial_reports, all_pass=True),
    }
