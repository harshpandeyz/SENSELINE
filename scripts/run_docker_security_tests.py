"""Run and record Docker isolation regression tests; no fallback to host candidates."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.secure_execution import SANDBOX_IMAGE, SecureExecutionUnavailable, docker_preflight


def main() -> int:
    try:
        preflight = docker_preflight(SANDBOX_IMAGE)
    except SecureExecutionUnavailable as exc:
        report = {
            "status": "NOT RUN",
            "reason": str(exc),
            "test_cases_passed": 0,
            "test_cases_skipped": 0,
            "docker_image": SANDBOX_IMAGE,
            "checks_executed": False,
        }
        destination = ROOT / "results" / "docker_security_validation.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2
    command = [sys.executable, "-m", "pytest", "-q", "tests/test_benchmark.py", "-m", "docker_integration"]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    output = run.stdout + run.stderr
    match = re.search(r"(?m)^(\d+) passed(?:, (\d+) skipped)?(?:, (\d+) deselected)?", output)
    passed = int(match.group(1)) if match else 0
    skipped = int(match.group(2) or 0) if match else 0
    report = {
        "status": "PASS" if run.returncode == 0 and match and skipped == 0 else "FAIL",
        # Keep the reproducible arguments without publishing a host account path.
        "command": [Path(sys.executable).name, *command[1:]],
        "exit_code": run.returncode,
        "test_cases_passed": passed,
        "test_cases_skipped": skipped,
        "docker_image": preflight["image"],
        "docker_image_id": preflight["image_id"],
        "docker_isolation_probe": preflight["isolation_probe"],
        "checks": [
            "host environment isolation", "outside host path isolation", "hidden fixture isolation",
            "network disabled", "evaluator/runtime files read-only and absent host path inaccessible",
            "non-root UID", "all capability sets dropped", "no-new-privileges",
            "read-only root and candidate mounts", "CPU/memory/PID cgroup limits",
            "host wall timeout", "memory exhaustion is contained", "PID limit under fork pressure",
            "agent command not invoked if Docker preflight fails",
            "trusted reference code uses the same isolated candidate interface",
        ],
        "checks_executed": True,
        "stdout_stderr": output,
    }
    destination = ROOT / "results" / "docker_security_validation.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "stdout_stderr"}, indent=2))
    if run.returncode:
        print(output, file=sys.stderr)
    return run.returncode or (0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
