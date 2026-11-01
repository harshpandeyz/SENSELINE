import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graders.grade import TASK_DIRS, _schema_errors, compare, compute_metrics, grade_module, load_cases
from oracle.compute import SOLVERS
from reference import s01, s02, s03, s04, s05, s06, s07, s08
from harness.export_task import export_task
from harness.agent_environment import AgentEnvironmentError, build_agent_environment
from harness.secure_execution import CandidateExecutionError, DockerCandidate, SANDBOX_IMAGE, SecureExecutionUnavailable, docker_command, docker_preflight
from harness.run_trial import _run_agent_with_limits, _snapshot_candidate, run_trial
from harness.agent_usage import usage_from_event
from simulator.synthetic import encode_register_count, generate_measurements
from scripts.run_experiment import load_matrix, plan
from scripts.package_submission import REQUIRED as PACKAGE_REQUIRED, package as build_submission_package

REFERENCES = {"S01": s01, "S02": s02, "S03": s03, "S04": s04, "S05": s05, "S06": s06, "S07": s07, "S08": s08}
MUTATION_MANIFEST = json.loads((ROOT / "mutations" / "MUTATION_MANIFEST.json").read_text())


def load_trusted_control(path):
    """Load checked-in test controls only. User candidate files use DockerCandidate instead."""
    spec = importlib.util.spec_from_file_location("trusted_mutation_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("task", sorted(REFERENCES))
def test_reference_passes_all_hidden_vectors_and_output_schema(task):
    report = grade_module(task, REFERENCES[task], "reference")
    assert report["case_count"] >= 25
    assert report["passed"] == report["case_count"], [case for case in report["cases"] if not case["passed"]]


@pytest.mark.parametrize("task", sorted(SOLVERS))
def test_independent_oracle_alternative_passes(task):
    alternative = SimpleNamespace(solve=SOLVERS[task])
    report = grade_module(task, alternative, "independent-oracle")
    assert report["passed"] == report["case_count"]


@pytest.mark.parametrize("entry", MUTATION_MANIFEST["mutations"], ids=lambda entry: entry["file"])
def test_mutation_is_rejected_for_its_documented_reason(entry):
    path = ROOT / "mutations" / entry["file"]
    report = grade_module(entry["task"], load_trusted_control(path), path.stem)
    failed = [case for case in report["cases"] if not case["passed"]]
    assert failed, f"mutation survived: {path.name}"
    observed = {dimension for case in failed for dimension in case["failure_dimensions"]}
    assert set(entry["expected_failure_dimensions"]) & observed, (path.name, observed)
    if path.name == "S08_extra_schema_field.py":
        metrics = compute_metrics([report])
        assert report["passed"] == 0
        assert metrics["silent_corruption_rate"]["numerator"] == 0
        assert all(case["numerical_correct"] for case in report["cases"])


def test_s04_collects_simultaneous_errors_in_contract_order():
    vector = next(case for case in load_cases("S04") if case["id"] == "S04-simultaneous-independent-defects")
    expected = [
        "missing_serial_number", "measurand_mismatch", "calibration_not_current",
        "outside_validity_dates", "invalid_uncertainty", "unit_mismatch",
        "traceability_not_documented",
    ]
    assert s04.solve(vector["input"]) == SOLVERS["S04"](vector["input"]) == {"valid": False, "reasons": expected}


def test_s04_missing_combinations_skip_only_checks_that_need_missing_certificate_fields():
    cases = {case["id"]: case for case in load_cases("S04")}
    missing_date = cases["S04-missing-valid-from-plus-measurand"]
    assert s04.solve(missing_date["input"])["reasons"] == ["missing_valid_from", "measurand_mismatch"]
    missing_range = cases["S04-missing-range-max-plus-bad-value"]
    assert s04.solve(missing_range["input"])["reasons"] == ["missing_range_max", "invalid_range_or_value"]
    missing_fields = cases["S04-missing-serial-and-unit"]
    assert s04.solve(missing_fields["input"])["reasons"] == ["missing_serial_number", "missing_unit"]


def test_s04_inclusive_date_and_range_boundaries_remain_valid():
    cases = {case["id"]: case for case in load_cases("S04")}
    for name in ("valid-start", "valid-end", "range-low", "range-high"):
        assert s04.solve(cases["S04-" + name]["input"]) == {"valid": True, "reasons": []}


def test_s08_has_more_than_25_cases_and_explicit_cross_layer_scenarios():
    cases = {case["id"]: case for case in load_cases("S08")}
    assert len(cases) >= 25
    assert len([name for name in cases if name.startswith("S08-")]) == len(cases)
    expected_names = {
        "S08-fahrenheit-calibrated-correlated-full-pipeline",
        "S08-signed-negative-with-environmental-compensation",
        "S08-two-correlated-rectangular-contributors",
        "S08-uncertainty-supplied-after-calibration-not-rescaled",
        "S08-type-a-observations-already-in-final-unit",
        "S08-fahrenheit-output-units-and-celsius-temperature-interval",
        "S08-calibrated-result-touches-upper-conformity-boundary",
        "S08-calibration-range-inclusive-low", "S08-calibration-range-inclusive-high",
        "S08-calibration-range-exclusive-below", "S08-calibration-range-exclusive-above",
        "S08-valid-certificate-with-stale-sensor-data",
        "S08-stale-invalid-uncertainty-and-invalid-certificate",
    }
    assert expected_names <= set(cases)
    for name in expected_names:
        vector = cases[name]
        assert s08.solve(vector["input"]) == SOLVERS["S08"](vector["input"]) == vector["expected"]

    fahrenheit = cases["S08-fahrenheit-calibrated-correlated-full-pipeline"]["expected"]
    assert fahrenheit["physical_quantity"] == {"value": "20", "unit": "C"}
    assert fahrenheit["corrected_measurement"] == {"value": "20.35", "unit": "C"}
    assert abs(Decimal(fahrenheit["standard_uncertainty"]) - Decimal("0.1")) < Decimal("1e-16")
    assert Decimal(fahrenheit["expanded_uncertainty"]) == Decimal("0.2")
    assert fahrenheit["conformity_decision"] == "ACCEPT" and fahrenheit["valid"] is True

    signed = cases["S08-signed-negative-with-environmental-compensation"]["expected"]
    assert signed["decoded_measurement"]["raw_count"] == -50
    assert signed["corrected_measurement"]["value"] == "-4.9"
    assert signed["conformity_decision"] == "ACCEPT"

    covariance = cases["S08-two-correlated-rectangular-contributors"]["expected"]
    assert abs(Decimal(covariance["standard_uncertainty"]) - Decimal(1)) < Decimal("1e-16")
    assert covariance["expanded_uncertainty"] == "2"

    # These independently hand-checkable cases distinguish post-calibration
    # uncertainty inputs from raw-input uncertainty that would require gain
    # propagation.  Here the task explicitly supplies the budget in final C.
    post_cal_case = cases["S08-uncertainty-supplied-after-calibration-not-rescaled"]
    post_cal = post_cal_case["expected"]
    assert post_cal["corrected_measurement"] == {"value": "51", "unit": "C"}
    assert abs(Decimal(post_cal["standard_uncertainty"]) - Decimal("0.6") / Decimal(3).sqrt()) < Decimal("1e-16")
    assert abs(Decimal(post_cal["expanded_uncertainty"]) - Decimal("1.2") / Decimal(3).sqrt()) < Decimal("1e-16")
    # If 0.6 were mistakenly multiplied by gain=2, U would be 1.38564 C and
    # this otherwise valid measurement would become indeterminate.
    assert post_cal["conformity_decision"] == "ACCEPT"

    type_a = cases["S08-type-a-observations-already-in-final-unit"]["expected"]
    assert type_a["corrected_measurement"] == {"value": "37", "unit": "C"}
    assert abs(Decimal(type_a["standard_uncertainty"]) - Decimal(1) / Decimal(3).sqrt()) < Decimal("1e-16")
    assert abs(Decimal(type_a["expanded_uncertainty"]) - Decimal(2) / Decimal(3).sqrt()) < Decimal("1e-16")

    fahrenheit_output = cases["S08-fahrenheit-output-units-and-celsius-temperature-interval"]["expected"]
    assert fahrenheit_output["physical_quantity"] == {"value": "77", "unit": "F"}
    # Delta-T is +5 °C, so the coefficient contributes +1 °F. Treating the
    # interval as +9 °F would incorrectly produce 79.7 °F.
    assert fahrenheit_output["corrected_measurement"] == {"value": "78.9", "unit": "F"}
    assert abs(Decimal(fahrenheit_output["standard_uncertainty"]) - Decimal("0.3") / Decimal(3).sqrt()) < Decimal("1e-16")
    assert fahrenheit_output["conformity_decision"] == "ACCEPT"

    touching = cases["S08-calibrated-result-touches-upper-conformity-boundary"]["expected"]
    assert touching["corrected_measurement"]["value"] == "25.6"
    assert touching["conformity_interval"]["upper"] == "26.1"
    assert touching["conformity_decision"] == "ACCEPT"

    assert cases["S08-calibration-range-inclusive-low"]["expected"]["calibration_validity"]["valid"] is True
    assert cases["S08-calibration-range-inclusive-high"]["expected"]["calibration_validity"]["valid"] is True
    assert cases["S08-calibration-range-exclusive-below"]["expected"]["calibration_validity"]["valid"] is False
    assert cases["S08-calibration-range-exclusive-above"]["expected"]["calibration_validity"]["valid"] is False
    assert cases["S08-calibration-range-exclusive-below"]["expected"]["corrected_measurement"]["value"] == "-0.01"
    assert cases["S08-calibration-range-exclusive-above"]["expected"]["corrected_measurement"]["value"] == "40.01"

    stale = cases["S08-valid-certificate-with-stale-sensor-data"]["expected"]
    assert stale["calibration_validity"]["valid"] is True
    assert stale["temporal_validity"]["reason"] == "stale_timestamp"
    assert stale["valid"] is False and stale["conformity_decision"] == "INDETERMINATE"

    multi = cases["S08-stale-invalid-uncertainty-and-invalid-certificate"]["expected"]
    assert multi["error_reasons"] == [
        "temporal:stale_timestamp", "uncertainty:negative_half_width",
        "certificate:calibration_not_current", "certificate:outside_validity_dates",
        "certificate:traceability_not_documented",
    ]
    assert multi["conformity_decision"] == "INDETERMINATE"


def test_hand_calculated_golden_outputs_remain_independently_checked():
    raw = {"frame_hex": "80", "width_bits": 8, "byte_order": "big", "signed": True, "scale": "1", "rounding_places": 0}
    assert s01.solve(raw) == SOLVERS["S01"](raw) == {"valid": True, "raw_count": -128, "value": "-128"}
    units = {"value": "68", "from_unit": "F", "to_unit": "C", "rounding_places": 2}
    assert s02.solve(units) == SOLVERS["S02"](units) == {"valid": True, "value": "20.00", "unit": "C"}
    cal = {"raw_value": "3", "gain": "2", "offset": "4", "temp_coefficient": "0.5", "ambient_temperature_c": "30", "reference_temperature_c": "20", "correction_state": "RAW", "rounding_places": 2}
    assert s03.solve(cal) == SOLVERS["S03"](cal) == {"valid": True, "corrected_value": "15.00"}
    cert = {"serial_number": "X", "measurand": "pressure", "status": "CURRENT", "valid_from": "2026-01-01", "valid_to": "2026-12-31", "range_min": "0", "range_max": "2", "uncertainty": "0", "unit": "Pa", "traceability_chain_status": "DOCUMENTED"}
    measure = {"serial_number": "X", "measurand": "pressure", "date": "2026-06-01", "value": "1", "unit": "Pa"}
    evidence = {"certificate": cert, "measurement": measure}
    assert s04.solve(evidence) == SOLVERS["S04"](evidence) == {"valid": True, "reasons": []}
    uncertainty = {"components": [{"kind": "type_a", "observations": ["1", "2", "3"], "sensitivity": "1"}], "coverage_factor": "2"}
    output = s05.solve(uncertainty)
    assert output == SOLVERS["S05"](uncertainty)
    assert Decimal(output["combined_standard_uncertainty"]) == Decimal("0.5773502691896257645091487805019574556476")
    decision = {"y": "0", "expanded_uncertainty": "1", "lower_limit": "-1", "upper_limit": "1"}
    assert s06.solve(decision) == SOLVERS["S06"](decision) == {"valid": True, "lower": "-1", "upper": "1", "decision": "ACCEPT"}
    temporal = {"timestamp_ms": 1000, "now_ms": 1000, "max_age_ms": 0, "allowed_future_skew_ms": 0, "sequence": 0, "last_sequence": 4294967295}
    assert s07.solve(temporal) == SOLVERS["S07"](temporal) == {"valid": True, "reason": "ok", "sequence_order": "NEWER"}


def test_public_examples_match_schemas_and_independent_oracle():
    for task, path in TASK_DIRS.items():
        examples = json.loads((path / "public_examples.json").read_text())
        assert len(examples) >= 3
        input_schema = json.loads((path / "input.schema.json").read_text())
        output_schema = json.loads((path / "output.schema.json").read_text())
        for example in examples:
            Draft202012Validator(input_schema).validate(example["input"])
            Draft202012Validator(output_schema).validate(example["expected"])
            assert example["expected"] == SOLVERS[task](example["input"])


def test_export_contains_only_agent_visible_task_material(tmp_path):
    target = export_task("S01", tmp_path / "export")
    names = {path.name for path in target.iterdir()}
    assert names == {"task.md", "input.schema.json", "output.schema.json", "public_examples.json", "solution.py", "AGENT_README.md"}
    assert not any("hidden" in path.name or "grader" in path.name for path in target.iterdir())
    assert "NotImplementedError" in (target / "solution.py").read_text()


def test_hidden_generator_is_seed_reproducible():
    paths = sorted((ROOT / "graders" / "hidden").glob("S*.json"))
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_hidden_vectors.py")], cwd=ROOT, check=True, capture_output=True, text=True)
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    assert before == after


def test_synthetic_sensor_simulator_is_seed_reproducible_and_handles_rollover():
    first = generate_measurements(77, 5, width_bits=8, byte_order="little")
    second = generate_measurements(77, 5, width_bits=8, byte_order="little")
    assert first == second
    assert [row["sequence"] for row in first[:4]] == [4294967294, 4294967295, 0, 1]
    assert all(row["frame_hex"] == encode_register_count(row["count"], 8, "little", True) for row in first)


def test_scr_schema_only_failure_does_not_inflate_silent_corruption_rate():
    class ExtraField:
        @staticmethod
        def solve(payload):
            result = dict(SOLVERS["S01"](payload))
            result["debug"] = "harmless"
            return result

    report = grade_module("S01", ExtraField, "schema-only-extra-field")
    metrics = compute_metrics([report])
    assert report["passed"] == 0 and report["case_count"] > 0
    assert all(not row["schema_valid"] for row in report["cases"])
    assert all(row["numerical_correct"] for row in report["cases"])
    assert metrics["contract_violations"]["numerator"] == report["case_count"]
    assert metrics["silent_corruption_rate"] == {"numerator": 0, "denominator": report["case_count"], "value": 0.0}


def test_numeric_format_type_violation_fails_schema_but_not_physical_accuracy():
    class NumericInsteadOfDecimalString:
        @staticmethod
        def solve(payload):
            result = SOLVERS["S01"](payload)
            if result.get("valid") and Decimal(result["value"]) == Decimal(result["value"]).to_integral_value():
                result["value"] = int(Decimal(result["value"]))
            return result

    report = grade_module("S01", NumericInsteadOfDecimalString, "numeric-json-format")
    successful = [row for row in report["cases"] if isinstance(row["expected"], dict) and row["expected"].get("valid") is True and Decimal(row["expected"]["value"]) == Decimal(row["expected"]["value"]).to_integral_value()]
    assert successful
    assert all(not row["schema_valid"] and row["numerical_correct"] for row in successful)
    assert all(not row["silent_corruption"] for row in successful)


def test_s02_equivalent_fahrenheit_pair_is_contract_failure_not_physical_corruption():
    class SourceUnitOutput:
        @staticmethod
        def solve(payload):
            result = s02.solve(payload)
            if result.get("valid") and payload["from_unit"] == "F" and payload["to_unit"] == "C":
                return {"valid": True, "value": payload["value"], "unit": "F"}
            return result

    report = grade_module("S02", SourceUnitOutput, "equivalent-source-unit")
    equivalent = [row for row in report["cases"] if row["id"] in ("S02-seeded-01", "S02-seeded-11")]
    assert len(equivalent) == 2
    assert all(not row["passed"] and row["contract_violation"] for row in equivalent)
    assert all(row["numerical_correct"] and row["physical_equivalence_correct"] for row in equivalent)
    assert all(not row["physical_unit_correct"] and not row["silent_corruption"] for row in equivalent)
    diag = next(item for item in equivalent[0]["numerical_diagnostics"] if item["field"] == "value")
    assert diag["actual"] == "-0.005" and diag["actual_unit"] == "F"
    assert Decimal(diag["comparison_actual"]) == Decimal("-17.78056")


@pytest.mark.parametrize("kind,expected_physical", [("wrong_label", False), ("missing_unit", False), ("incompatible", False), ("extra_field", True)])
def test_s02_unit_corruption_and_schema_only_cases_are_separated(kind, expected_physical):
    target_ids = {"S02-seeded-01", "S02-seeded-11"}

    class UnitDefect:
        @staticmethod
        def solve(payload):
            result = s02.solve(payload)
            if result.get("valid") and payload["from_unit"] == "F" and payload["to_unit"] == "C":
                if kind == "wrong_label":
                    return {**result, "unit": "F"}
                if kind == "missing_unit":
                    return {key: value for key, value in result.items() if key != "unit"}
                if kind == "incompatible":
                    return {**result, "unit": "Pa"}
                return {**result, "debug": "harmless"}
            return result

    report = grade_module("S02", UnitDefect, kind)
    affected = [row for row in report["cases"] if row["id"] in target_ids]
    assert affected
    metrics = compute_metrics([report])
    assert all(row["physical_equivalence_correct"] is expected_physical for row in affected)
    if kind == "extra_field":
        assert all(not row["schema_valid"] and not row["silent_corruption"] for row in affected)
    elif kind == "missing_unit":
        assert all(not row["schema_valid"] and row["numerical_correct"] for row in affected)
        assert all(row["semantic_integrity_failure"] and not row["silent_corruption"] for row in affected)
        assert metrics["semantic_integrity_failures"]["numerator"] >= len(affected)
    else:
        assert all(row["silent_corruption"] for row in affected)
        assert metrics["silent_corruption_rate"]["numerator"] >= len(affected)


def test_s08_unit_pair_equivalence_is_separate_from_required_canonical_unit():
    case_id = "S08-fahrenheit-calibrated-correlated-full-pipeline"

    class FahrenheitRepresentation:
        @staticmethod
        def solve(payload):
            result = s08.solve(payload)
            if payload.get("sensor", {}).get("frame_hex") == "02A8":
                result["physical_quantity"] = {"value": "68", "unit": "F"}
                result["corrected_measurement"] = {"value": "68.63", "unit": "F"}
            return result

    report = grade_module("S08", FahrenheitRepresentation, "equivalent-fahrenheit-representation")
    row = next(item for item in report["cases"] if item["id"] == case_id)
    assert not row["passed"] and row["contract_violation"]
    assert row["physical_equivalence_correct"] and row["numerical_correct"]
    assert not row["physical_unit_correct"] and not row["silent_corruption"]


def test_s08_decoded_measurement_requires_from_unit_and_grades_scr_across_all_45_cases():
    path = ROOT / "mutations" / "S08_decoded_unit_label.py"
    report = grade_module("S08", load_trusted_control(path), path.stem)
    metrics = compute_metrics([report])
    assert report["case_count"] == 45
    rows = report["cases"]
    inputs = {case["id"]: case["input"] for case in load_cases("S08")}
    valid_expected = [row for row in rows if row["expected"].get("valid") is True]
    assert valid_expected
    for row in rows:
        decoded = row["actual"].get("decoded_measurement")
        if isinstance(decoded, dict):
            assert decoded["unit"] == "Pa"
        diagnostic = next((item for item in row["unit_diagnostics"] if item["field"] == "decoded_measurement"), None)
        if isinstance(row["expected"].get("decoded_measurement"), dict):
            assert diagnostic is not None
            assert diagnostic["expected_unit"] == inputs[row["id"]]["units"]["from_unit"]
            assert not diagnostic["unit_correct"]
    assert metrics["silent_corruption_rate"]["numerator"] == len(valid_expected)
    assert all("incorrect_physical_measurement_or_unit_claimed_valid" in row["silent_corruption_reasons"] for row in valid_expected)


def test_s08_equivalent_decoded_representation_is_contract_failure_only():
    target_id = "S08-fahrenheit-calibrated-correlated-full-pipeline"

    class EquivalentDecodedCelsius:
        @staticmethod
        def solve(payload):
            result = s08.solve(payload)
            if payload["units"]["from_unit"] == "F" and isinstance(result.get("decoded_measurement"), dict):
                value_f = Decimal(result["decoded_measurement"]["value"])
                value_c = (value_f - Decimal(32)) * Decimal(5) / Decimal(9)
                result["decoded_measurement"]["value"] = str(value_c)
                result["decoded_measurement"]["unit"] = "C"
            return result

    report = grade_module("S08", EquivalentDecodedCelsius, "equivalent-decoded-unit-pair")
    row = next(item for item in report["cases"] if item["id"] == target_id)
    decoded = next(item for item in row["unit_diagnostics"] if item["field"] == "decoded_measurement")
    assert not row["passed"] and row["contract_violation"]
    assert not decoded["unit_correct"] and decoded["physically_equivalent"]
    assert not row["silent_corruption"]


@pytest.mark.parametrize("unit", ["Pa", None])
def test_s08_incompatible_or_missing_unit_with_valid_claim_is_classified_correctly(unit):
    case_id = "S08-fahrenheit-calibrated-correlated-full-pipeline"

    class WrongUnit:
        @staticmethod
        def solve(payload):
            result = s08.solve(payload)
            if payload.get("sensor", {}).get("frame_hex") == "02A8" and result.get("physical_quantity"):
                if unit is None:
                    result["physical_quantity"].pop("unit")
                else:
                    result["physical_quantity"]["unit"] = unit
            return result

    report = grade_module("S08", WrongUnit, "invalid-physical-unit")
    row = next(item for item in report["cases"] if item["id"] == case_id)
    assert row["actual"]["valid"] is True
    assert not row["physical_equivalence_correct"]
    if unit is None:
        assert row["numerical_correct"] and row["semantic_integrity_failure"]
        assert not row["silent_corruption"]
    else:
        assert row["silent_corruption"]


def test_missing_unit_with_wrong_numeric_value_is_silent_corruption():
    class MissingUnitAndWrongValue:
        @staticmethod
        def solve(payload):
            result = s02.solve(payload)
            if result.get("valid") and payload["from_unit"] == "F" and payload["to_unit"] == "C":
                result["value"] = "999"
                result.pop("unit")
            return result

    report = grade_module("S02", MissingUnitAndWrongValue, "missing-unit-wrong-value")
    affected = [row for row in report["cases"] if row["id"] in {"S02-seeded-01", "S02-seeded-11"}]
    assert affected and all(row["semantic_integrity_failure"] and row["silent_corruption"] for row in affected)


def test_incorrect_values_marked_valid_are_silent_corruption():
    class WrongPhysicalValue:
        @staticmethod
        def solve(payload):
            result = SOLVERS["S01"](payload)
            if result.get("valid"):
                result["value"] = "999999"
            return result

    report = grade_module("S01", WrongPhysicalValue, "wrong-value-valid")
    rows = [row for row in report["cases"] if row["expected"].get("valid") is True]
    assert rows and all(row["silent_corruption"] for row in rows)
    assert all("incorrect_physical_measurement_or_unit_claimed_valid" in row["silent_corruption_reasons"] for row in rows)


def test_invalid_calibration_marked_valid_is_silent_corruption():
    class InvalidCertificateAccepted:
        @staticmethod
        def solve(payload):
            result = SOLVERS["S04"](payload)
            if not result["valid"]:
                return {"valid": True, "reasons": []}
            return result

    report = grade_module("S04", InvalidCertificateAccepted, "invalid-cert-valid")
    bad = [row for row in report["cases"] if row["expected"].get("valid") is False]
    assert bad and all(row["silent_corruption"] for row in bad)
    assert all("invalid_measurement_or_calibration_marked_valid" in row["silent_corruption_reasons"] for row in bad)


def test_unsafe_acceptance_has_correct_ground_truth_denominator():
    class AlwaysAccept:
        @staticmethod
        def solve(payload):
            result = SOLVERS["S06"](payload)
            if result.get("valid"):
                result["decision"] = "ACCEPT"
                return result
            return {"valid": True, "lower": "0", "upper": "0", "decision": "ACCEPT"}

    report = grade_module("S06", AlwaysAccept, "unsafe-accept")
    metrics = compute_metrics([report])
    truth_nonacceptable = sum(case["expected_disposition"] != "ACCEPT" for case in report["cases"])
    unsafe = sum(case["actual_disposition"] == "ACCEPT" for case in report["cases"] if case["expected_disposition"] != "ACCEPT")
    assert metrics["unsafe_acceptance_rate"] == {"numerator": unsafe, "denominator": truth_nonacceptable, "value": unsafe / truth_nonacceptable}
    assert unsafe > 0


@pytest.mark.parametrize("response", [None, "not-json-object", []], ids=["null", "string", "array"])
def test_malformed_outputs_fail_contract_without_automatically_counting_scr(response):
    report = grade_module("S01", SimpleNamespace(solve=lambda _payload: response), "malformed")
    metrics = compute_metrics([report])
    assert report["passed"] == 0
    assert metrics["contract_violations"]["numerator"] == report["case_count"]
    assert metrics["silent_corruption_rate"]["numerator"] == 0


def test_explicit_invalid_input_rejection_is_correct_not_corruption():
    vector = next(case for case in load_cases("S01") if case["id"] == "S01-truncated")
    assert vector["expected"]["valid"] is False
    output = s01.solve(vector["input"])
    assert output == vector["expected"]
    assert output["valid"] is False


def test_numerical_reporting_keeps_units_and_tolerances_per_field():
    report = grade_module("S02", s02, "reference")
    metrics = compute_metrics([report])
    assert "numerical_error_by_field_unit" in metrics
    assert not any(key in metrics for key in ("numerical_error_mean_absolute", "numerical_error_mean"))
    diagnostics = [item for row in report["cases"] for item in row["numerical_diagnostics"]]
    assert diagnostics
    required = {"field", "unit", "expected", "actual", "absolute_error", "relative_error", "permitted_tolerance", "normalized_error"}
    assert all(required <= set(item) for item in diagnostics)
    groups = metrics["numerical_error_by_field_unit"]
    assert any("[C]" in key for key in groups) and any("[Pa]" in key for key in groups)


def test_symbolic_units_are_explicit_in_task_contracts_and_numeric_reports():
    for task in ("S03", "S05", "S06"):
        contract = next(path for path in (ROOT / "tasks").iterdir() if path.name.startswith(task + "_")).joinpath("task.md").read_text()
        assert "symbolic" in contract and "`MU`" in contract
        report = grade_module(task, REFERENCES[task], "reference")
        diagnostics = [item for row in report["cases"] for item in row["numerical_diagnostics"]]
        assert diagnostics and all(item["unit"].startswith("MU ") for item in diagnostics)


def test_uncertainty_accuracy_is_not_penalized_by_unrelated_s08_physical_value_error():
    class WrongCorrectedValueOnly:
        @staticmethod
        def solve(payload):
            result = s08.solve(payload)
            if result.get("corrected_measurement"):
                result["corrected_measurement"]["value"] = "999"
            return result

    report = grade_module("S08", WrongCorrectedValueOnly, "physical-only-defect")
    metrics = compute_metrics([report])
    assert metrics["uncertainty_calculation_accuracy"]["value"] == 1.0
    assert metrics["numerical_correctness"]["value"] < 1.0


def test_task_metrics_expose_independent_denominators():
    for task, module in REFERENCES.items():
        report = grade_module(task, module, "reference")
        metrics = compute_metrics([report])
        task_metrics = metrics["per_task"][task]
        for name in ("functional_correctness", "schema_compliance", "numerical_correctness", "validity_state_correctness", "execution_failures", "silent_corruption_rate"):
            assert "numerator" in task_metrics[name] and "denominator" in task_metrics[name]
        assert metrics["silent_corruption_rate"]["denominator"] == report["case_count"]
        if task not in ("S06", "S08"):
            assert metrics["unsafe_acceptance_rate"]["denominator"] == 0


def test_tolerance_is_field_specific_and_explicit():
    assert compare("S05", {"combined_standard_uncertainty": "1"}, {"combined_standard_uncertainty": "1.00000000000000005"})[0]
    assert not compare("S05", {"combined_standard_uncertainty": "1"}, {"combined_standard_uncertainty": "1.0000000000000002"})[0]
    assert compare("S05", {"standard_uncertainties": ["1"]}, {"standard_uncertainties": ["1.00000000000000005"]})[0]
    assert not compare("S01", {"value": "1"}, {"value": "1.0000000000000001"})[0]


def test_secure_docker_command_has_required_restrictions(tmp_path):
    solution = tmp_path / "solution.py"
    runtime = tmp_path / "runtime.py"
    solution.write_text("def solve(payload): return payload")
    runtime.write_text("pass")
    command = docker_command(solution, runtime, "senseline-test")
    joined = " ".join(command)
    for required in ("--network=none", "--user=65534:65534", "--cap-drop=ALL", "--security-opt=no-new-privileges:true", "--read-only", "--pids-limit=32", "--memory=128m", "--cpus=0.50", "--tmpfs", SANDBOX_IMAGE, "readonly"):
        assert required in joined
    assert command.count("--mount") == 2
    assert "--env-file" not in command and "-e" not in command


@pytest.mark.docker_integration
def test_secure_trial_fails_closed_before_agent_command_without_docker(monkeypatch, tmp_path):
    import harness.run_trial as runner
    marker = tmp_path / "agent-was-run"
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"name": "must-not-run", "command": [sys.executable, "-c", f"open({str(marker)!r},'w').write('bad')"], "version_command": []}))
    monkeypatch.setattr(runner, "docker_preflight", lambda _image: (_ for _ in ()).throw(SecureExecutionUnavailable("secure model evaluation unavailable: forced test failure")))
    with pytest.raises(SecureExecutionUnavailable, match="secure model evaluation unavailable"):
        runner.run_trial("S01", profile, "must-not-call", 1, 10, tmp_path / "results")
    assert not marker.exists()


def test_run_trial_never_imports_candidate_directly(monkeypatch, tmp_path):
    import harness.run_trial as runner
    observed = {}
    monkeypatch.setenv("SENSELINE_INJECTED_SECRET", "never-inherit-this")
    monkeypatch.setenv("GITHUB_TOKEN", "github-not-for-agent")
    monkeypatch.setattr(runner, "docker_preflight", lambda _image: {"docker_path": "/fake/docker", "image": SANDBOX_IMAGE, "image_id": "sha256:test"})
    emitted = '{"type":"thread.started","thread_id":"thread-test"}\n{"type":"item.completed","item":{"type":"command_execution","command":"python -m pytest"}}\n'
    monkeypatch.setattr(runner.subprocess, "run", lambda command, **kwargs: observed.update({"command": command, "env": kwargs.get("env")}) or SimpleNamespace(returncode=0, stdout=emitted, stderr=""))
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"name": "local-smoke", "command": [sys.executable, "-c", "print('mock agent')"], "version_command": [], "structured_stdout_jsonl": True}))
    monkeypatch.setattr(runner, "DockerCandidate", lambda *args, **kwargs: SimpleNamespace(solve=lambda payload: {"valid": False, "reason": "mock execution"}))
    # A fresh task export plus a mocked Docker adapter exercises transcript plumbing without executing source.
    result = runner.run_trial("S01", profile, "smoke-only", 1, 5, tmp_path / "results")
    assert "SENSELINE_INJECTED_SECRET" not in observed["env"]
    assert "GITHUB_TOKEN" not in observed["env"]
    assert observed["env"]["HOME"] != os.environ.get("HOME")
    assert observed["env"]["HOME"].endswith(".senseline-agent-home")
    assert result["candidate_source_sha256"]
    event_log = (tmp_path / "results" / "runs" / result["run_id"] / "events.jsonl").read_text()
    assert "candidate_execution_completed" not in event_log  # mock facade exposes no Docker event writer
    transcript = tmp_path / "results" / "transcripts" / f"{result['run_id']}.jsonl"
    lines = [json.loads(line) for line in transcript.read_text().splitlines()]
    captured_events = [item["data"] for item in lines if item.get("event") == "agent_reported_structured_event" and item.get("source") == "agent_stdout_jsonl"]
    assert [item["type"] for item in captured_events] == ["thread.started", "item.completed"]
    assert captured_events[1]["item"]["command"] == "python -m pytest"
    complete = next(item["data"] for item in lines if item["event"] == "complete_transcript")
    assert complete["exact_task_instruction"] and complete["candidate_source_sha256"] == result["candidate_source_sha256"]
    assert '"thread.started"' in complete["agent_stdout"]


def test_agent_environment_is_allowlisted_and_uses_fresh_task_local_credentials_home(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    host_home = tmp_path / "host-home"
    host_codex = host_home / ".codex"
    host_codex.mkdir(parents=True)
    (host_codex / "auth.json").write_text("host-session-secret")
    source_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(host_home),
        "GITHUB_TOKEN": "gh-secret",
        "AWS_SECRET_ACCESS_KEY": "aws-secret",
        "DATABASE_URL": "postgres-secret",
        "SENSELINE_INJECTED_SECRET": "injected-secret",
        "OPENAI_API_KEY": "dedicated-test-key",
    }
    env, audit = build_agent_environment(
        {"name": "codex-cli", "credential_env": ["OPENAI_API_KEY"]}, {}, workspace, source_env,
    )
    assert env["OPENAI_API_KEY"] == "dedicated-test-key"
    for name in ("GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY", "DATABASE_URL", "SENSELINE_INJECTED_SECRET"):
        assert name not in env
    assert env["HOME"] != str(host_home)
    assert Path(env["CODEX_HOME"]).is_relative_to(workspace)
    assert not (Path(env["CODEX_HOME"]) / "auth.json").exists()
    assert audit["host_home_inherited"] is False and audit["codex_home_is_task_local_and_fresh"]
    config = (Path(env["CODEX_HOME"]) / "config.toml").read_text()
    assert 'inherit = "none"' in config and 'enabled = false' in config
    assert "dedicated-test-key" not in config


def test_agent_environment_requires_explicit_dedicated_provider_credential(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with pytest.raises(AgentEnvironmentError, match="dedicated provider credential OPENAI_API_KEY"):
        build_agent_environment(
            {"name": "codex-cli", "credential_env": ["OPENAI_API_KEY"]}, {}, workspace,
            {"PATH": "/usr/bin:/bin"},
        )


def test_provider_usage_metadata_is_recorded_as_estimated_not_confirmed_cost():
    usage = usage_from_event({"type": "turn.completed", "usage": {"input_tokens": 1000, "output_tokens": 250, "total_tokens": 1250, "cost_usd": 0.003}})
    assert usage == {
        "input_tokens": 1000,
        "output_tokens": 250,
        "total_tokens": 1250,
        "agent_reported_cost_usd": "0.003",
        "source_event_type": "turn.completed",
        "billing_cost_confirmed": False,
    }


def test_agent_usage_limit_stops_process_and_cost_estimate_is_not_confirmed(tmp_path):
    source = (
        "import json,time; "
        "print(json.dumps({'type':'turn.completed','usage':{'input_tokens':100,'output_tokens':100,'total_tokens':200}}),flush=True); "
        "time.sleep(5)"
    )
    report = _run_agent_with_limits(
        [sys.executable, "-c", source], tmp_path,
        {"PATH": os.environ.get("PATH", os.defpath)}, 10,
        token_budget=150, max_cost_usd=1,
        input_rate=2.0, output_rate=4.0,
    )
    assert report["usage"]["budget_stop_reason"] == "token_budget_exceeded"
    assert report["usage"]["total_tokens"] == 200
    assert Decimal(report["usage"]["estimated_cost_usd"]) == Decimal("0.0006")
    assert report["usage"]["confirmed_cost_usd"] is None
    assert report["runtime_seconds"] < 3


def test_agent_estimated_cost_cap_stops_process(tmp_path):
    source = (
        "import json,time; "
        "print(json.dumps({'type':'turn.completed','usage':{'input_tokens':1000,'output_tokens':1000,'total_tokens':2000}}),flush=True); "
        "time.sleep(5)"
    )
    report = _run_agent_with_limits(
        [sys.executable, "-c", source], tmp_path,
        {"PATH": os.environ.get("PATH", os.defpath)}, 10,
        token_budget=5000, max_cost_usd=0.001,
        input_rate=1.0, output_rate=1.0,
    )
    assert report["usage"]["budget_stop_reason"] == "estimated_trial_cost_cap_exceeded"
    assert Decimal(report["usage"]["estimated_cost_usd"]) == Decimal("0.002")
    assert report["runtime_seconds"] < 3


def test_agent_created_candidate_symlink_is_not_followed_into_host_files(tmp_path):
    workspace = tmp_path / "agent-workspace"
    snapshot = tmp_path / "snapshot"
    workspace.mkdir()
    secret = tmp_path / "host-secret.txt"
    secret.write_text("must not be copied")
    (workspace / "solution.py").symlink_to(secret)

    candidate, issue = _snapshot_candidate(workspace, snapshot)
    assert issue and "regular file" in issue
    assert candidate.read_text() == ""
    assert "must not be copied" not in candidate.read_text()


def test_experiment_plan_is_72_trials_and_never_calls_agents_without_execute(tmp_path):
    template = json.loads((ROOT / "configs" / "experiment_matrix.template.json").read_text())
    for index, item in enumerate(template["configurations"], 1):
        item["model_id"] = f"test/model-{index}"
        item["agent_version_expected"] = f"test-agent-{index}"
    matrix_file = tmp_path / "matrix.json"
    matrix_file.write_text(json.dumps(template))
    matrix = load_matrix(matrix_file)
    full = plan(matrix, "full")
    pilot = plan(matrix, "pilot")
    assert full["planned_trial_count"] == 72
    assert pilot["planned_trial_count"] == 9 and pilot["task_scope"] == ["S01", "S05", "S08"]
    assert full["paid_api_calls_started"] is False
    unconfigured = load_matrix.__globals__["ROOT"] / "configs" / "experiment_matrix.template.json"
    with pytest.raises(ValueError, match="exact model_id"):
        load_matrix(unconfigured)


def test_unconfigured_experiment_template_has_dry_run_pilot_and_full_plans():
    template = ROOT / "configs" / "experiment_matrix.template.json"
    matrix = load_matrix(template, require_models=False)
    pilot = plan(matrix, "pilot")
    full = plan(matrix, "full")
    assert pilot["planned_trial_count"] == 9
    assert pilot["task_scope"] == ["S01", "S05", "S08"]
    assert full["planned_trial_count"] == 72
    assert pilot["paid_api_calls_started"] is False and full["paid_api_calls_started"] is False


def test_release_package_is_flat_and_excludes_credentials_and_dev_artifacts(tmp_path):
    project = tmp_path / "source"
    project.mkdir()
    required = set(PACKAGE_REQUIRED)
    for task_number in range(1, 9):
        task_root = f"tasks/s{task_number:02}_test"
        required.update(f"{task_root}/{leaf}" for leaf in ("task.md", "input.schema.json", "output.schema.json", "public_examples.json", "solution.py"))
    for relative in required:
        target = project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}\n", encoding="utf-8")
    (project / "FINAL_AUDIT_REPORT.md").write_text("external release report\n")
    (project / ".env").write_text("SECRET=value\n")
    (project / ".DS_Store").write_bytes(b"junk")
    (project / ".venv" / "bin").mkdir(parents=True)
    (project / ".venv" / "bin" / "python").write_text("binary")
    (project / "nested.zip").write_bytes(b"zip")
    archive = project / "dist" / "SENSELINE_submission.zip"
    report = build_submission_package(project, archive)
    assert report["flat_root_readme"] and report["task_package_count"] == 8
    with zipfile.ZipFile(archive) as zipped:
        names = set(zipped.namelist())
    assert "README.md" in names
    assert not any(name.startswith("SENSELINE/") for name in names)
    assert not any(name in {".env", ".DS_Store", "FINAL_AUDIT_REPORT.md", "nested.zip"} for name in names)
    assert not any(name.startswith(".venv/") for name in names)
    assert len(list(archive.parent.glob("*.zip"))) == 1


def test_paid_experiment_requires_registered_cost_cap_and_provider_hard_limit(monkeypatch, tmp_path):
    import scripts.run_experiment as runner
    template = json.loads((ROOT / "configs" / "experiment_matrix.template.json").read_text())
    for index, item in enumerate(template["configurations"], 1):
        item["model_id"] = f"test/model-{index}"
        item["agent_version_expected"] = f"test-agent-{index}"
        item["budget"]["max_cost_per_trial_usd"] = 1
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(json.dumps(template))
    matrix = runner.load_matrix(matrix_path)
    invoked = []
    monkeypatch.setattr(runner, "docker_preflight", lambda *_: invoked.append("docker"))
    with pytest.raises(RuntimeError, match="positive spend_control.max_total_cost_usd"):
        runner.execute(matrix, "pilot")
    assert not invoked


def _docker_ready():
    try:
        docker_preflight()
        return True
    except SecureExecutionUnavailable:
        return False


DOCKER_READY = _docker_ready()


@pytest.mark.docker_integration
@pytest.mark.skipif(not DOCKER_READY, reason="secure Docker integration unavailable: daemon or pinned image missing")
def test_malicious_candidates_cannot_access_host_env_files_hidden_tests_network_or_modify_evaluator(tmp_path, monkeypatch):
    host_marker = tmp_path / "outside-workspace-secret.txt"
    host_marker.write_text("host-only-regression-sentinel")
    monkeypatch.setenv("SENSELINE_REGRESSION_SECRET", "host-env-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "provider-key-must-not-enter-candidate")
    attacks = {
        "environment": 'import os\ndef solve(payload): return {"exposed": os.getenv("SENSELINE_REGRESSION_SECRET") is not None or os.getenv("OPENAI_API_KEY") is not None}',
        "outside_host_file": f'from pathlib import Path\ndef solve(payload):\n try: return {{"exposed": Path({str(host_marker)!r}).read_text() == "host-only-regression-sentinel"}}\n except Exception: return {{"exposed": False}}',
        "hidden_fixtures": f'from pathlib import Path\ndef solve(payload): return {{"exposed": any(Path(p).exists() for p in ("/grader/hidden/S01.json", "/opt/senseline/graders/hidden/S01.json", "/hidden/S01.json", {str(ROOT / "graders" / "hidden" / "S01.json")!r}))}}',
        "network": 'import socket\ndef solve(payload):\n try:\n  socket.create_connection(("1.1.1.1", 53), timeout=0.5); return {"connected": True}\n except OSError: return {"connected": False}',
        "evaluator_write": 'from pathlib import Path\ndef solve(payload):\n try:\n  Path("/runtime/runner.py").write_text("tampered"); return {"modified": True}\n except OSError: return {"modified": False}',
    }
    for label, source_text in attacks.items():
        source = tmp_path / f"attack-{label}.py"
        source.write_text(source_text)
        output = DockerCandidate(source).solve({})
        assert output in ({"exposed": False}, {"connected": False}, {"modified": False}), (label, output)


@pytest.mark.docker_integration
@pytest.mark.skipif(not DOCKER_READY, reason="secure Docker integration unavailable: daemon or pinned image missing")
@pytest.mark.parametrize("task", sorted(REFERENCES))
def test_reference_solution_uses_same_isolated_execution_interface(task, tmp_path):
    wrapper = tmp_path / "solution.py"
    wrapper.write_text(f"from reference.{task.lower()} import solve\n")
    candidate = DockerCandidate(wrapper, support_mounts=[(ROOT / "reference", "/support/reference")])
    vector = load_cases(task)[0]
    assert candidate.solve(vector["input"]) == vector["expected"]


@pytest.mark.docker_integration
@pytest.mark.skipif(not DOCKER_READY, reason="secure Docker integration unavailable: daemon or pinned image missing")
def test_candidate_container_enforces_identity_capability_filesystem_and_resource_limits(tmp_path):
    source = tmp_path / "solution.py"
    source.write_text('''import os
from pathlib import Path
def solve(payload):
    status = Path("/proc/self/status").read_text()
    return {
        "uid": os.geteuid(),
        "no_new_privs": "NoNewPrivs:\\t1" in status,
        "capabilities_empty": "CapEff:\\t0000000000000000" in status and "CapBnd:\\t0000000000000000" in status,
        "cpu_limit": Path("/sys/fs/cgroup/cpu.max").read_text().strip(),
        "memory_limit": Path("/sys/fs/cgroup/memory.max").read_text().strip(),
        "process_limit": Path("/sys/fs/cgroup/pids.max").read_text().strip(),
        "root_read_only": not os.access("/etc", os.W_OK),
        "candidate_mount_read_only": not os.access("/candidate", os.W_OK),
    }
''', encoding="utf-8")
    result = DockerCandidate(source).solve({})
    assert result == {
        "uid": 65534, "no_new_privs": True, "capabilities_empty": True,
        "cpu_limit": "50000 100000", "memory_limit": "134217728", "process_limit": "32",
        "root_read_only": True, "candidate_mount_read_only": True,
    }


@pytest.mark.docker_integration
@pytest.mark.skipif(not DOCKER_READY, reason="secure Docker integration unavailable: daemon or pinned image missing")
def test_candidate_cpu_wall_timeout_memory_and_process_limits_are_enforced(tmp_path):
    timeout_source = tmp_path / "timeout.py"
    timeout_source.write_text("def solve(payload):\n    while True: pass\n", encoding="utf-8")
    with pytest.raises(CandidateExecutionError, match="exceeded 0.5s execution limit"):
        DockerCandidate(timeout_source, timeout_seconds=0.5).solve({})

    memory_source = tmp_path / "memory.py"
    memory_source.write_text("def solve(payload):\n    value = bytearray(256 * 1024 * 1024)\n    return {'allocated': len(value)}\n", encoding="utf-8")
    with pytest.raises(CandidateExecutionError):
        DockerCandidate(memory_source, timeout_seconds=5).solve({})

    process_source = tmp_path / "processes.py"
    process_source.write_text('''import os
import time
def solve(payload):
    children = []
    for _ in range(40):
        try:
            child = os.fork()
        except OSError:
            break
        if child == 0:
            time.sleep(0.3)
            os._exit(0)
        children.append(child)
    for child in children:
        os.waitpid(child, 0)
    return {"created": len(children)}
''', encoding="utf-8")
    process_result = DockerCandidate(process_source, timeout_seconds=5).solve({})
    assert process_result["created"] < 40
