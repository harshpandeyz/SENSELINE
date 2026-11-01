"""Build the flat, sanitized SENSELINE submission ZIP and SHA-256 sidecar."""
from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
ARCHIVE = DIST / "SENSELINE_submission.zip"
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024

EXCLUDED_DIRS = {
    ".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".tox", "node_modules", "build", "dist", "__MACOSX",
}
EXCLUDED_NAMES = {
    ".DS_Store", "auth.json", "credentials.json", "id_rsa", "id_ed25519",
    "credentials", "secrets", "secrets.json", "secret.json",
    # The release report contains the final archive digest and is delivered beside the ZIP.
    "FINAL_AUDIT_REPORT.md",
    # This report is created only after the package is built; including it would
    # create a self-referential release digest.
    "archive_validation.json",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".zip", ".pem", ".p12", ".pfx", ".key", ".token", ".log", ".tmp", ".bak", ".orig"}
REQUIRED = {
    "README.md", "requirements.txt", ".env.example", ".gitignore", "Makefile", "Dockerfile", "pyproject.toml",
    "SUBMISSION_CHECKLIST.md", "graders/grade.py", "oracle/compute.py", "harness/secure_execution.py",
    "harness/candidate_runtime.py", "scripts/run_experiment.py", "scripts/validate_submission.py",
    "scripts/package_submission.py", "scripts/verify_release_archive.py", "mutations/MUTATION_MANIFEST.json",
    "tests/test_benchmark.py", "docs/METHODOLOGY.md", "docs/RELATED_WORK.md",
    "docs/FAILURE_ANALYSIS.md", "docs/video_walkthrough_script.md",
    "docs/INDEPENDENT_REVIEW_PACKAGE.md", "presentation/SENSELINE_walkthrough.html",
    "results/experiment_status.json", "results/reference_validation.json",
    "results/submission_status.json",
    "results/unit_integrity_validation.json", "results/docker_security_validation.json",
    "results/agent_security_validation.json", "results/opencode_permission_verification.json",
}
TASK_LEAVES = ("task.md", "input.schema.json", "output.schema.json", "public_examples.json", "solution.py")


def excluded(relative: Path) -> bool:
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return True
    name = relative.name
    if name in EXCLUDED_NAMES or name == ".env":
        return True
    if name.startswith(".env.") and name != ".env.example":
        return True
    if relative.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    lowered = name.lower()
    return lowered.startswith("credentials.") or lowered.startswith("secrets.")


def archive_members(root: Path = ROOT) -> list[Path]:
    selected = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if excluded(relative) or path.is_dir():
            continue
        if path.is_symlink():
            raise ValueError(f"refusing to package symlink: {relative.as_posix()}")
        try:
            if stat.S_ISREG(path.lstat().st_mode):
                selected.append(path)
        except FileNotFoundError:
            continue
    return sorted(selected, key=lambda item: item.relative_to(root).as_posix())


def validate_members(names: set[str]) -> None:
    missing = sorted(REQUIRED - names)
    if missing:
        raise ValueError("submission archive is missing required files: " + ", ".join(missing))
    task_roots = sorted({"/".join(Path(name).parts[:2]) for name in names if name.startswith("tasks/") and len(Path(name).parts) > 2})
    if len(task_roots) != 8:
        raise ValueError(f"expected eight task packages, found {task_roots}")
    for task_root in task_roots:
        missing_task_files = [f"{task_root}/{leaf}" for leaf in TASK_LEAVES if f"{task_root}/{leaf}" not in names]
        if missing_task_files:
            raise ValueError("task package is incomplete: " + ", ".join(missing_task_files))
    if any(name.startswith("SENSELINE/") for name in names):
        raise ValueError("archive must be flat with README.md directly at the ZIP root")
    if "README.md" not in names:
        raise ValueError("README.md must be directly at the ZIP root")


def package(root: Path = ROOT, archive: Path = ARCHIVE) -> dict:
    root = Path(root).resolve()
    archive = Path(archive).resolve()
    if not (root / "README.md").is_file():
        raise ValueError("project root README.md is missing")
    files = archive_members(root)
    archive.parent.mkdir(parents=True, exist_ok=True)
    # Remove stale archives in dist so exactly one release archive remains.
    for stale in archive.parent.glob("*.zip"):
        stale.unlink()

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=False) as zf:
        for path in files:
            relative = path.relative_to(root).as_posix()
            zf.write(path, arcname=relative)

    size = archive.stat().st_size
    if size >= MAX_ARCHIVE_BYTES:
        archive.unlink(missing_ok=True)
        raise ValueError(f"submission archive must be below 50 MiB; got {size} bytes")
    with zipfile.ZipFile(archive) as zf:
        bad_member = zf.testzip()
        if bad_member:
            raise ValueError(f"archive CRC check failed for {bad_member}")
        names = set(zf.namelist())
        validate_members(names)
        prohibited = [name for name in names if excluded(Path(name))]
        if prohibited:
            raise ValueError("archive contains excluded/private artifacts: " + ", ".join(prohibited[:10]))

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum_path = archive.with_suffix(archive.suffix + ".sha256")
    checksum_path.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    zips = list(archive.parent.glob("*.zip"))
    if zips != [archive]:
        raise ValueError(f"dist must contain exactly {archive.name}")
    return {
        "archive": str(archive), "archive_size_bytes": size,
        "archive_sha256": digest, "file_count": len(files),
        "flat_root_readme": True, "task_package_count": 8,
        "nested_archives": 0, "checksum_file": str(checksum_path),
    }


def main() -> int:
    try:
        report = package()
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "reason": f"{type(exc).__name__}: {exc}"}, indent=2))
        return 1
    print(json.dumps({"status": "PASS", **report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
