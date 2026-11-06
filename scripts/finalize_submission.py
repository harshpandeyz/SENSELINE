"""Video-aware finalization: insert real public video URL and rebuild the final ZIP.

Usage:
    python scripts/finalize_submission.py --video-url "ACTUAL_PUBLIC_VIDEO_URL"

Candidate state (before owner publishes):
    README contains: Video walkthrough: VIDEO_URL_PENDING_OWNER_RECORDING ...
    Candidate ZIP: dist/SENSELINE_SUBMISSION_CANDIDATE.zip (candidate validation PASS, VIDEO_URL PENDING)

Final state (after owner supplies a real public https URL):
    This script validates the URL, updates the exact README video line
    (idempotent), rebuilds dist/SENSELINE_FINAL_SUBMISSION.zip with the official
    package inclusion/exclusion rules, enforces README-at-root + 50 MiB + SHA-256
    sidecar, extracts to a fresh temp dir, verifies required files + video URL,
    runs submission validation in final mode, and reports.

Never invents a URL. Never writes a test URL into the real README or final ZIP
(test with a temporary copy only).
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CANDIDATE_NAME = "SENSELINE_SUBMISSION_CANDIDATE.zip"
FINAL_NAME = "SENSELINE_FINAL_SUBMISSION.zip"
PLACEHOLDER = "VIDEO_URL_PENDING_OWNER_RECORDING"

BANNED_SUBSTRINGS = (
    "example.com", "example.org", "example.net", "example.edu",
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
    "placeholder", "pending", "todo", "xxx", "your-video", "insert-url",
    "video_url_pending", "change-me", "replace-me",
)


def validate_video_url(url: str) -> str:
    cleaned = (url or "").strip()
    if not cleaned:
        raise ValueError("video URL is blank; supply the real public video URL")
    if PLACEHOLDER in cleaned or "PENDING" in cleaned.upper() and "https://" not in cleaned:
        raise ValueError(f"video URL still contains the placeholder ({PLACEHOLDER}); supply the real public URL")
    lowered = cleaned.lower()
    if cleaned.startswith("file://") or lowered.startswith("file:"):
        raise ValueError("file:// URLs are not public video links")
    if not cleaned.startswith("https://"):
        raise ValueError("video URL must be a public https:// link (got non-https or blank scheme)")
    if " " in cleaned or "\n" in cleaned:
        raise ValueError("video URL must not contain whitespace")
    if "." not in cleaned.split("://", 1)[1]:
        raise ValueError("video URL does not look like a public host (missing dot)")
    if len(cleaned) < 12:
        raise ValueError("video URL is too short to be legitimate")
    if any(token in lowered for token in BANNED_SUBSTRINGS):
        raise ValueError(f"video URL looks like a placeholder/example/local link: {cleaned}")
    return cleaned


def update_readme_video_line(readme_path: Path, url: str) -> dict:
    text = readme_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    target = None
    for i, line in enumerate(lines):
        if line.startswith("Video walkthrough:"):
            target = i
            break
    if target is None:
        raise ValueError("README is missing its 'Video walkthrough:' line")
    old = lines[target]
    new_line = f"Video walkthrough: {url} — five-minute public walkthrough (see docs/video_walkthrough_script.md)."
    # Idempotent: if the exact video line already carries the URL, do not duplicate sections.
    already = (old == new_line)
    if already:
        # Still ensure no stale release-status placeholder contradicts the published URL.
        # The release-status line mentions the placeholder token as an instruction; after
        # publication it must not claim the video is unpublished.
        status_updated = False
        for j, line in enumerate(lines):
            if line.startswith("**Release status:**") and PLACEHOLDER in line and "not published" in line:
                lines[j] = line.replace(f"(`{PLACEHOLDER}`; finalize via `python scripts/finalize_submission.py --video-url \"ACTUAL_PUBLIC_VIDEO_URL\"`)", f"({url})").replace(" and the video is not published", " and the video is published")
                status_updated = True
        if status_updated:
            readme_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return {"updated": True, "old": old, "new": new_line, "note": "release-status line updated"}
        return {"updated": False, "old": old, "new": old}
    lines[target] = new_line
    # Keep the release-status line consistent: replace the unpublished-video note with the URL.
    for j, line in enumerate(lines):
        if line.startswith("**Release status:**") and PLACEHOLDER in line:
            lines[j] = line.replace(f"(`{PLACEHOLDER}`; finalize via `python scripts/finalize_submission.py --video-url \"ACTUAL_PUBLIC_VIDEO_URL\"`)", f"({url})").replace(" and the video is not published", " and the video is published")
    readme_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"updated": True, "old": old, "new": new_line}


def build_final_archive() -> dict:
    from scripts.package_submission import package
    archive = ROOT / "dist" / FINAL_NAME
    # package() resolves ARCHIVE from env; force final name.
    os.environ["SENSELINE_ARCHIVE_NAME"] = FINAL_NAME
    # Re-import to pick up env? package() uses ARCHIVE constant evaluated at import;
    # call package(root, archive) explicitly to avoid env staleness.
    report = package(root=ROOT, archive=archive)
    return report


def verify_final_archive(expected_url: str) -> dict:
    from scripts.package_submission import MAX_ARCHIVE_BYTES
    archive = ROOT / "dist" / FINAL_NAME
    checksum_path = archive.with_suffix(archive.suffix + ".sha256")
    if not archive.is_file() or not checksum_path.is_file():
        raise ValueError("final ZIP or SHA-256 sidecar is missing after rebuild")
    size = archive.stat().st_size
    if size >= MAX_ARCHIVE_BYTES:
        raise ValueError(f"final ZIP exceeds 50 MiB: {size} bytes")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    expected_digest, expected_name = checksum_path.read_text(encoding="ascii").strip().split(maxsplit=1)
    if expected_digest != digest or expected_name != archive.name:
        raise ValueError("SHA-256 sidecar does not match the final archive")
    with zipfile.ZipFile(archive) as zf:
        bad = zf.testzip()
        if bad:
            raise ValueError(f"ZIP CRC failure: {bad}")
        names = zf.namelist()
        if "README.md" not in names or any(n.startswith("SENSELINE/") for n in names):
            raise ValueError("README.md must be at the flat ZIP root")
        # Required-file scan (mirrors verify_release_archive REQUIRED subset).
        required = {
            "README.md", "requirements.txt", "SUBMISSION_CHECKLIST.md",
            "scripts/validate_submission.py", "graders/grade.py",
            "oracle/compute.py", "harness/secure_execution.py",
            "docs/METHODOLOGY.md", "docs/FAILURE_ANALYSIS.md",
            "docs/video_walkthrough_script.md",
            "presentation/SENSELINE_walkthrough.html",
            "results/experiment_analysis.json",
        }
        missing = sorted(required - set(names))
        if missing:
            raise ValueError("final archive missing required files: " + ", ".join(missing))
        task_roots = {"/".join(Path(n).parts[:2]) for n in names if n.startswith("tasks/") and len(Path(n).parts) > 2}
        if len(task_roots) != 8:
            raise ValueError(f"expected eight task packages, found {sorted(task_roots)}")
        with tempfile.TemporaryDirectory(prefix="senseline-finalize-verify-") as tmp:
            extracted = Path(tmp) / "extracted"
            extracted.mkdir()
            zf.extractall(extracted)
            readme_text = (extracted / "README.md").read_text(encoding="utf-8")
            video_lines = [ln for ln in readme_text.splitlines() if ln.startswith("Video walkthrough:")]
            if not video_lines:
                raise ValueError("extracted README missing 'Video walkthrough:' line")
            if expected_url not in video_lines[0] or PLACEHOLDER in video_lines[0]:
                raise ValueError("extracted README does not carry the supplied public video URL")
            # The video line itself must be clean; other docs may legitimately mention the
            # placeholder token name as an instruction (audit reports, this script's docs), so
            # only the extracted video line is enforced here. The release-status line is
            # updated by update_readme_video_line to avoid contradicting the published URL.
    return {
        "archive": archive.name, "size_bytes": size, "sha256": digest,
        "zip_crc_valid": True, "flat_root_readme": True,
        "video_url_in_archive": expected_url,
    }


def run_final_validation() -> dict:
    import subprocess
    proc = subprocess.run(
        [sys.executable, "scripts/validate_submission.py", "--mode", "final"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
    )
    return {
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Insert real video URL and rebuild the final ZIP (idempotent).")
    parser.add_argument("--video-url", required=True, help='Real public video URL, e.g. "https://youtu.be/..."')
    args = parser.parse_args()
    try:
        url = validate_video_url(args.video_url)
    except ValueError as exc:
        print(f"FINALIZATION_FAIL: {exc}")
        return 1
    try:
        readme_report = update_readme_video_line(ROOT / "README.md", url)
        build_report = build_final_archive()
        verify_report = verify_final_archive(url)
        validation = run_final_validation()
        if validation["exit_code"] != 0:
            print("FINALIZATION_FAIL: submission validation in final mode failed")
            print(validation["stdout_tail"])
            print(validation["stderr_tail"])
            return 1
        print("FINALIZATION_PASS")
        print(f"VIDEO_URL: {url}")
        print(f"README_UPDATED: {readme_report['updated']}")
        print(f"ARCHIVE: {build_report['archive']} ({build_report['archive_size_bytes']} bytes, sha256 {build_report['archive_sha256']})")
        print(f"VERIFY: CRC ok, README-at-root ok, video URL verified in fresh extraction")
        print(f"SUBMISSION_VALIDATION_FINAL_MODE: PASS")
        print(f"SUBMISSION_READINESS: READY (video published; owner review + quota rerun still tracked in submission_status.json)")
        return 0
    except Exception as exc:  # noqa: BLE001 - report and fail closed
        print(f"FINALIZATION_FAIL: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
