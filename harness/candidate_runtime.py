"""Small trusted JSON-line adapter mounted read-only into the candidate container."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import traceback
from pathlib import Path


def main() -> int:
    if sys.version_info[:3] != (3, 11, 18):
        print(json.dumps({"ok": False, "error": f"unexpected pinned Python runtime: {sys.version.split()[0]}"}))
        return 2
    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "error": "runtime requires one candidate path"}))
        return 2
    source = Path(sys.argv[1])
    spec = importlib.util.spec_from_file_location("senseline_candidate", source)
    if spec is None or spec.loader is None:
        print(json.dumps({"ok": False, "error": "candidate could not be loaded"}))
        return 2
    module = importlib.util.module_from_spec(spec)
    candidate_stdout, candidate_stderr = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(candidate_stdout), contextlib.redirect_stderr(candidate_stderr):
            spec.loader.exec_module(module)
            solve = getattr(module, "solve", None)
            if not callable(solve):
                raise TypeError("candidate must define callable solve(payload)")
            payload = json.load(sys.stdin)
            output = solve(payload)
            try:
                output = json.loads(json.dumps(output, allow_nan=False, ensure_ascii=False))
            except (TypeError, ValueError, RecursionError):
                output = {"__non_json_candidate_output__": type(output).__name__}
        record = {
            "ok": True,
            "output": output,
            "candidate_stdout": candidate_stdout.getvalue(),
            "candidate_stderr": candidate_stderr.getvalue(),
        }
    except BaseException as exc:  # candidate exceptions become a grader-visible execution failure
        record = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(limit=8),
            "candidate_stdout": candidate_stdout.getvalue(),
            "candidate_stderr": candidate_stderr.getvalue(),
        }
    sys.__stdout__.write(json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
    sys.__stdout__.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
