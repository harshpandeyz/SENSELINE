"""Securely grade a candidate file using the pinned Docker execution adapter."""
import argparse
import json
import sys
from pathlib import Path

from .grade import compute_metrics, grade_module
from harness.secure_execution import DockerCandidate, SANDBOX_IMAGE, SecureExecutionUnavailable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=[f"S{i:02}" for i in range(1, 9)])
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--timeout", type=float, default=5.0, help="per-input candidate wall timeout")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        candidate = DockerCandidate(args.candidate, timeout_seconds=args.timeout, image=SANDBOX_IMAGE)
    except SecureExecutionUnavailable as exc:
        print(json.dumps({"status": "SECURE_EVALUATION_UNAVAILABLE", "reason": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(2)
    try:
        report = grade_module(args.task, candidate, str(args.candidate))
    except SecureExecutionUnavailable as exc:
        print(json.dumps({"status": "SECURE_EVALUATION_UNAVAILABLE", "reason": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(2)
    report["metrics"] = compute_metrics([report])
    output = json.dumps(report, indent=2, ensure_ascii=False, default=str)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    raise SystemExit(0 if report["passed"] == report["case_count"] else 1)


if __name__ == "__main__":
    main()
