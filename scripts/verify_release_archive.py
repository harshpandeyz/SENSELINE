"""Extract the release into a fresh directory and validate it independently."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "dist" / os.environ.get("SENSELINE_ARCHIVE_NAME", "SENSELINE_submission.zip")
CHECKSUM = ARCHIVE.with_suffix(ARCHIVE.suffix + ".sha256")
MAX_BYTES = 50 * 1024 * 1024
REQUIRED = {
    "README.md", "requirements.txt", "SUBMISSION_CHECKLIST.md",
    "scripts/validate_submission.py", "scripts/run_docker_security_tests.py",
    "scripts/verify_agent_security.py", "scripts/verify_opencode_permissions.py",
    "scripts/package_submission.py", "scripts/finalize_submission.py", "scripts/run_experiment.py",
    "graders/grade.py", "oracle/compute.py", "harness/secure_execution.py",
    "reference/s01.py", "reference/s02.py", "reference/s03.py", "reference/s04.py",
    "reference/s05.py", "reference/s06.py", "reference/s07.py", "reference/s08.py",
    "mutations/MUTATION_MANIFEST.json",
    "docs/METHODOLOGY.md", "docs/RELATED_WORK.md", "docs/FAILURE_ANALYSIS.md",
    "docs/video_walkthrough_script.md", "docs/INDEPENDENT_REVIEW_PACKAGE.md",
    "presentation/SENSELINE_walkthrough.html", "results/experiment_status.json",
    "results/reference_validation.json", "results/unit_integrity_validation.json",
    "results/docker_security_validation.json", "results/agent_security_validation.json",
    "results/opencode_permission_verification.json",
}
FORBIDDEN_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules", "__MACOSX"}
FORBIDDEN_SUFFIXES = {".zip", ".pyc", ".pyo", ".pem", ".p12", ".pfx", ".key", ".token"}
FORBIDDEN_NAMES = {"auth.json", "credentials", "credentials.json", "secrets", "secrets.json", "secret.json", "id_rsa", "id_ed25519"}


def _check_names(names: list[str]) -> None:
    name_set = set(names)
    missing = sorted(REQUIRED - name_set)
    if missing:
        raise RuntimeError("archive is missing required files: " + ", ".join(missing))
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise RuntimeError(f"unsafe archive path: {name}")
        if any(part in FORBIDDEN_PARTS for part in path.parts):
            raise RuntimeError(f"development artifact in archive: {name}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES or name == ".DS_Store":
            raise RuntimeError(f"prohibited file in archive: {name}")
        if path.name.lower() in FORBIDDEN_NAMES or path.name.lower().startswith("credentials.") or path.name.lower().startswith("secrets."):
            raise RuntimeError(f"credential-like file in archive: {name}")
        if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
            raise RuntimeError(f"environment secret file in archive: {name}")
    if "README.md" not in name_set or any(name.startswith("SENSELINE/") for name in names):
        raise RuntimeError("README.md must be at the flat ZIP root")
    task_roots = {"/".join(PurePosixPath(name).parts[:2]) for name in names if name.startswith("tasks/") and len(PurePosixPath(name).parts) > 2}
    if len(task_roots) != 8:
        raise RuntimeError(f"expected eight task packages, found {sorted(task_roots)}")
    for task_root in task_roots:
        for leaf in ("task.md", "input.schema.json", "output.schema.json", "public_examples.json", "solution.py"):
            if f"{task_root}/{leaf}" not in name_set:
                raise RuntimeError(f"incomplete task package: {task_root}/{leaf}")


def _run(command: list[str], cwd: Path, timeout: int = 1800) -> dict:
    start = time.monotonic()
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    record = {
        "command": command, "exit_code": result.returncode,
        "runtime_seconds": round(time.monotonic() - start, 3),
        "stdout_tail": result.stdout[-6000:], "stderr_tail": result.stderr[-3000:],
    }
    if result.returncode:
        raise RuntimeError(json.dumps(record, indent=2))
    return record


def verify(archive: Path = ARCHIVE, checksum: Path = CHECKSUM, mode: str = "candidate") -> dict:
    archive = Path(archive).resolve()
    checksum = Path(checksum).resolve()
    if not archive.is_file() or not checksum.is_file():
        raise RuntimeError("submission ZIP or SHA-256 sidecar is missing")
    size = archive.stat().st_size
    if size >= MAX_BYTES:
        raise RuntimeError(f"archive is not below 50 MiB: {size} bytes")
    present = sorted(p.name for p in archive.parent.glob("*.zip"))
    allowed = {"SENSELINE_SUBMISSION_CANDIDATE.zip", "SENSELINE_FINAL_SUBMISSION.zip", "SENSELINE_submission.zip"}
    unknown = [name for name in present if name not in allowed]
    if unknown:
        raise RuntimeError(f"dist contains unknown archives: {unknown}")
    if archive.name not in present:
        raise RuntimeError(f"dist must contain {archive.name}")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    expected_digest, expected_name = checksum.read_text(encoding="ascii").strip().split(maxsplit=1)
    if expected_digest != digest or expected_name != archive.name:
        raise RuntimeError("SHA-256 sidecar does not match the archive")

    start = time.monotonic()
    with zipfile.ZipFile(archive) as zf:
        bad = zf.testzip()
        if bad:
            raise RuntimeError(f"ZIP CRC failure: {bad}")
        names = zf.namelist()
        if len(names) != len(set(names)):
            raise RuntimeError("archive has duplicate member paths")
        _check_names(names)
        example_env = zf.read(".env.example").decode("utf-8")
        for line in example_env.splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                if line.split("=", 1)[1].strip():
                    raise RuntimeError(".env.example contains a non-empty credential value")
        for info in zf.infolist():
            file_mode = info.external_attr >> 16
            if file_mode and (file_mode & 0o170000) == 0o120000:
                raise RuntimeError(f"archive contains a symbolic link: {info.filename}")

        with tempfile.TemporaryDirectory(prefix="senseline-release-verify-") as temporary:
            extracted = Path(temporary) / "extracted"
            extracted.mkdir()
            zf.extractall(extracted)
            if not (extracted / "README.md").is_file():
                raise RuntimeError("README.md did not extract at the archive root")

            venv_path = Path(temporary) / "venv"
            import venv
            venv.EnvBuilder(with_pip=True, clear=True).create(venv_path)
            if os.name == "nt":
                python = venv_path / "Scripts" / "python.exe"
            else:
                python = venv_path / "bin" / "python"
            commands = []
            commands.append(_run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", "requirements.txt"], extracted, 900))
            commands.append(_run([str(python), "-m", "pytest", "-q"], extracted, 1800))
            validate_mode = "final" if mode == "final" else "candidate"
            commands.append(_run([str(python), "scripts/validate_submission.py", "--mode", validate_mode], extracted, 1800))
            commands.append(_run([str(python), "scripts/run_docker_security_tests.py"], extracted, 1800))
            commands.append(_run([str(python), "scripts/verify_agent_security.py"], extracted, 180))
            commands.append(_run([str(python), "scripts/verify_opencode_permissions.py"], extracted, 180))

            security_records = []
            for script in ("docker_security_validation.json", "agent_security_validation.json", "opencode_permission_verification.json"):
                report_path = extracted / "results" / script
                if not report_path.is_file():
                    raise RuntimeError(f"security verifier did not produce {report_path}")
                security_records.append(json.loads(report_path.read_text(encoding="utf-8")))
            if security_records[0].get("status") != "PASS" or security_records[0].get("test_cases_skipped") != 0:
                raise RuntimeError("Docker security checks did not all execute and pass")
            if security_records[1].get("status") != "PASS":
                raise RuntimeError("Codex workspace security checks did not pass")
            if security_records[2].get("status") != "CLI_CONFIG_RESOLVED":
                raise RuntimeError("OpenCode permission config was not resolved by the installed CLI")

            reference_report = json.loads((extracted / "results" / "reference_validation.json").read_text(encoding="utf-8"))
            video_status = reference_report.get("video_status", {"status": "UNKNOWN"})
            # Candidate mode allows the explicit placeholder and reports PENDING_VIDEO;
            # final mode rejects it and requires a published URL. A candidate ZIP must
            # never receive a final-submission PASS.
            if mode == "final" and video_status.get("status") != "PUBLISHED":
                raise RuntimeError("final mode requires a published public video URL; placeholder rejected")
            if video_status.get("status") != "PUBLISHED":
                video_blocker = "video walkthrough URL pending (project-owner action); technical package validates, submission readiness is blocked"
                technical = "PASS"
                readiness = "PENDING_VIDEO"
            else:
                video_blocker = None
                technical = "PASS"
                readiness = "READY" if mode == "final" else "READY_CANDIDATE_VIDEO_PRESENT"

            return {
                "status": technical, "archive": archive.name, "archive_size_bytes": size,
                "archive_sha256": digest, "zip_crc_valid": True, "flat_root_readme": True,
                "task_package_count": 8, "file_count": len(names), "fresh_extraction": True,
                "dependencies_installed_from_archive": True, "validation_commands": commands,
                "docker_security_status": security_records[0]["status"],
                "docker_security_tests_passed": security_records[0]["test_cases_passed"],
                "codex_security_status": security_records[1]["status"],
                "opencode_config_status": security_records[2]["status"],
                "video_status": video_status.get("status"),
                "video_release_blocker": video_blocker,
                "technical_package_validation": technical,
                "video_url": video_status.get("status"),
                "submission_readiness": readiness,
                "validation_mode": mode,
                "runtime_seconds": round(time.monotonic() - start, 3),
                "temporary_extraction_removed": True,
            }


def main() -> int:
    import argparse as _argparse
    _parser = _argparse.ArgumentParser()
    _parser.add_argument("--mode", choices=["candidate", "final"], default="candidate")
    _parser.add_argument("--archive", type=Path, default=ARCHIVE)
    _parser.add_argument("--checksum", type=Path, default=CHECKSUM)
    _parsed, _ = _parser.parse_known_args()
    # Resolve archive/checksum from explicit args or env-driven defaults.
    _archive = _parsed.archive if isinstance(_parsed.archive, Path) else Path(_parsed.archive)
    _checksum = _parsed.checksum if isinstance(_parsed.checksum, Path) else Path(_parsed.checksum)
    destination = ROOT / "results" / "archive_validation.json"
    try:
        report = verify(archive=_archive, checksum=_checksum, mode=_parsed.mode)
    except Exception as exc:
        report = {"status": "FAIL", "reason": f"{type(exc).__name__}: {exc}"}
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
