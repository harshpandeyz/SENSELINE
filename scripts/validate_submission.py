"""Validate task contracts, oracle/reference answers, mutations, and isolation."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graders.grade import TASK_DIRS, compute_metrics, grade_module, load_cases
from harness.export_task import export_task
from harness.secure_execution import DockerCandidate, SANDBOX_IMAGE, docker_preflight
from oracle.compute import SOLVERS
from reference import s01, s02, s03, s04, s05, s06, s07, s08

REFS = {"S01": s01, "S02": s02, "S03": s03, "S04": s04, "S05": s05, "S06": s06, "S07": s07, "S08": s08}
ROOT_FILES = (
    ".gitignore", "README.md", "requirements.txt", ".env.example", "Makefile", "Dockerfile", "pyproject.toml",
    "SUBMISSION_CHECKLIST.md", "docs/METHODOLOGY.md", "docs/RELATED_WORK.md",
    "docs/FAILURE_ANALYSIS.md", "docs/video_walkthrough_script.md",
    "docs/INDEPENDENT_REVIEW_PACKAGE.md", "presentation/SENSELINE_walkthrough.html",
    "configs/experiment_matrix.template.json", "configs/opencode_task_permissions.json",
    "scripts/package_submission.py", "scripts/verify_release_archive.py",
    "results/submission_status.json",
    "scripts/run_docker_security_tests.py", "scripts/verify_agent_security.py",
    "scripts/verify_opencode_permissions.py", "harness/secure_execution.py",
    "harness/candidate_runtime.py", "harness/agent_environment.py", "harness/agent_usage.py",
    "mutations/MUTATION_MANIFEST.json", "tests/test_benchmark.py", "oracle/compute.py",
)
TASK_FILES = ("task.md", "input.schema.json", "output.schema.json", "public_examples.json", "solution.py")
EXPORT_FILES = {*TASK_FILES, "AGENT_README.md"}


def _load_trusted_control(path: Path):
    spec = importlib.util.spec_from_file_location("trusted_control_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_task_exports() -> dict:
    exports = {}
    with tempfile.TemporaryDirectory(prefix="senseline-task-exports-") as temp:
        for task in sorted(REFS):
            destination = Path(temp) / task
            export_task(task, destination)
            names = {item.name for item in destination.iterdir()}
            if names != EXPORT_FILES:
                raise RuntimeError(f"{task} task export has unexpected files: {sorted(names)}")
            protected = [
                str(item.relative_to(destination)) for item in destination.rglob("*")
                if item.name.lower().startswith("hidden") or "grader" in item.name.lower() or "reference" in item.name.lower()
            ]
            if protected:
                raise RuntimeError(f"{task} task export contains protected material: {protected}")
            if "NotImplementedError" not in (destination / "solution.py").read_text(encoding="utf-8"):
                raise RuntimeError(f"{task} starter is not an unimplemented candidate template")
            exports[task] = {"status": "PASS", "visible_files": sorted(names), "protected_material_found": False}
    return exports


def _isolated_validation(preflight: dict, mutation_paths: list[Path]) -> dict:
    reference_cases = rejected_mutations = 0
    support = [(ROOT / "reference", "/support/reference")]
    with tempfile.TemporaryDirectory(prefix="senseline-reference-wrappers-") as temp:
        wrapper_dir = Path(temp)
        for task in sorted(REFS):
            wrapper = wrapper_dir / f"{task.lower()}_solution.py"
            wrapper.write_text(f"from reference.{task.lower()} import solve\n", encoding="utf-8")
            candidate = DockerCandidate(wrapper, timeout_seconds=5, image=SANDBOX_IMAGE, preflight=preflight, support_mounts=support)
            report = grade_module(task, candidate, "isolated-reference")
            if report["passed"] != report["case_count"]:
                failed = [row["id"] for row in report["cases"] if not row["passed"]]
                raise RuntimeError(f"isolated reference failed for {task}: {failed[:5]}")
            reference_cases += report["passed"]

        for path in mutation_paths:
            task = path.name[:3]
            candidate = DockerCandidate(path, timeout_seconds=5, image=SANDBOX_IMAGE, preflight=preflight, support_mounts=support)
            report = grade_module(task, candidate, path.stem)
            if report["passed"] == report["case_count"]:
                raise RuntimeError(f"isolated mutation survived: {path.name}")
            rejected_mutations += 1
    return {
        "status": "PASS", "sandbox_image": preflight["image"],
        "sandbox_image_id": preflight["image_id"], "reference_cases_passed": reference_cases,
        "mutation_controls_rejected": rejected_mutations,
    }


def main() -> int:
    missing = [path for path in ROOT_FILES if not (ROOT / path).is_file()]
    missing.extend(
        f"{task}/{name}" for task, folder in TASK_DIRS.items() for name in TASK_FILES
        if not (folder / name).is_file()
    )
    if missing:
        raise SystemExit("FAIL: missing required project files: " + ", ".join(missing))

    readmes = [path for path in ROOT.rglob("README.md") if not any(part in {".venv", ".pytest_cache", "__pycache__"} for part in path.parts)]
    if readmes != [ROOT / "README.md"]:
        raise SystemExit(f"FAIL: expected exactly one project README at the root; found {readmes}")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    video_markers = [line for line in readme.splitlines() if line.startswith("Video walkthrough:")]
    if not video_markers:
        raise SystemExit("FAIL: README is missing its 'Video walkthrough:' line")
    video_line = video_markers[0]
    if video_line.startswith("Video walkthrough: https://"):
        video_status = {"status": "PUBLISHED", "url": video_line.split(":", 1)[1].strip()}
    elif video_line.startswith("Video walkthrough: PENDING"):
        video_status = {"status": "PENDING_OWNER_ACTION", "note": video_line.split(":", 1)[1].strip()}
        print("WARNING: video walkthrough URL is pending (project-owner action); release is blocked on publication")
    else:
        raise SystemExit("FAIL: README video line must be a real 'https://' URL or an explicit 'PENDING' owner-action marker; placeholders are rejected")

    if set(TASK_DIRS) != set(REFS) or set(SOLVERS) != set(REFS):
        raise SystemExit("FAIL: task packages, references, and independent oracle do not match S01-S08")

    case_counts, reference_reports, total_reference = {}, [], 0
    for task, reference in REFS.items():
        cases = load_cases(task)
        case_counts[task] = len(cases)
        if len(cases) < 25:
            raise SystemExit(f"FAIL: {task} has fewer than 25 hidden vectors")
        for vector in cases:
            if SOLVERS[task](vector["input"]) != vector["expected"]:
                raise SystemExit(f"FAIL: independent oracle fixture mismatch: {vector['id']}")
            if reference.solve(vector["input"]) != vector["expected"]:
                raise SystemExit(f"FAIL: reference fixture mismatch: {vector['id']}")
        report = grade_module(task, reference, "trusted-reference")
        if report["passed"] != report["case_count"]:
            raise SystemExit(f"FAIL: reference schema/grade error for {task}")
        reference_reports.append(report)
        total_reference += report["passed"]

    mutation_manifest = json.loads((ROOT / "mutations/MUTATION_MANIFEST.json").read_text(encoding="utf-8"))
    mutation_paths = sorted((ROOT / "mutations").glob("S*.py"))
    manifest_by_file = {item["file"]: item for item in mutation_manifest["mutations"]}
    if mutation_manifest.get("mutation_count") != len(mutation_paths) or set(manifest_by_file) != {path.name for path in mutation_paths}:
        raise SystemExit("FAIL: mutation manifest does not enumerate every checked-in control")

    mutation_rows = []
    for path in mutation_paths:
        task = path.name[:3]
        report = grade_module(task, _load_trusted_control(path), path.stem)
        failed = [row for row in report["cases"] if not row["passed"]]
        dimensions = {dimension for row in failed for dimension in row["failure_dimensions"]}
        intended = set(manifest_by_file[path.name]["expected_failure_dimensions"])
        rejected = bool(failed) and bool(dimensions & intended)
        mutation_rows.append({
            "mutation": path.name, "task": task, "rejected": rejected,
            "cases_failed": len(failed), "case_count": report["case_count"],
            "observed_failure_dimensions": sorted(dimensions), "intended_failure_dimensions": sorted(intended),
            "silent_corruption_rate": compute_metrics([report])["silent_corruption_rate"],
        })
    if not all(row["rejected"] for row in mutation_rows):
        failed = [row["mutation"] for row in mutation_rows if not row["rejected"]]
        raise SystemExit("FAIL: mutations survived or failed for the wrong reason: " + ", ".join(failed))

    # Docker unavailability is a validation failure, never a host-Python fallback.
    preflight = docker_preflight(SANDBOX_IMAGE)
    isolated = _isolated_validation(preflight, mutation_paths)
    task_exports = _validate_task_exports()

    unit_path = ROOT / "mutations" / "S08_decoded_unit_label.py"
    unit_report = grade_module("S08", _load_trusted_control(unit_path), "S08_decoded_unit_label")
    unit_metrics = compute_metrics([unit_report])["silent_corruption_rate"]
    expected_valid = sum(case["expected"].get("valid") is True for case in load_cases("S08"))
    extra_path = ROOT / "mutations" / "S08_extra_schema_field.py"
    extra_report = grade_module("S08", _load_trusted_control(extra_path), "S08_extra_schema_field")
    extra_scr = compute_metrics([extra_report])["silent_corruption_rate"]["numerator"]
    decoded_checks = [
        row for row in unit_report["cases"]
        if isinstance(row["expected"].get("decoded_measurement"), dict)
    ]
    unit_integrity = {
        "status": "PASS" if (
            unit_report["case_count"] == 45
            and unit_metrics["numerator"] == expected_valid
            and extra_scr == 0
            and all(any(
                item["field"] == "decoded_measurement" and item["actual_unit"] == "Pa" and not item["unit_correct"]
                for item in row["unit_diagnostics"]
            ) for row in decoded_checks)
        ) else "FAIL",
        "s08_case_count": unit_report["case_count"],
        "wrong_decoded_unit_scr": unit_metrics,
        "expected_scr_numerator_for_valid_cases": expected_valid,
        "schema_only_extra_field_scr_numerator": extra_scr,
    }
    if unit_integrity["status"] != "PASS":
        raise SystemExit("FAIL: unit-integrity regression checks did not meet their expected rates")

    report = {
        "status": "PASS",
        "classification": "reference/oracle and deliberate mutation validation; not model results",
        "video_status": video_status,
        "task_case_counts": case_counts,
        "reference_cases_passed": total_reference,
        "reference_case_count": sum(case_counts.values()),
        "mutation_controls_rejected": sum(row["rejected"] for row in mutation_rows),
        "mutation_control_count": len(mutation_rows),
        "mutation_controls": mutation_rows,
        "isolated_candidate_execution": isolated,
        "task_export_validation": {"status": "PASS", "tasks": task_exports},
        "unit_integrity_validation": unit_integrity,
        "reference_metrics": compute_metrics(reference_reports),
    }
    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    (results / "reference_validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (results / "unit_integrity_validation.json").write_text(json.dumps(unit_integrity, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"], "reference_cases_passed": total_reference,
        "mutation_controls_rejected": len(mutation_rows), "isolated_candidate_execution": isolated["status"],
        "task_exports_validated": len(task_exports), "unit_integrity_validation": unit_integrity["status"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
