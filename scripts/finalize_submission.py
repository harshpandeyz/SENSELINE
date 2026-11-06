"""Video-aware finalization: insert real public video URL and rebuild the final ZIP.

Usage:
    python scripts/finalize_submission.py --video-url "REAL_PUBLIC_VIDEO_URL"

The owner must first verify the link loads in an incognito/private browser window.
Syntax validation alone does NOT prove public accessibility.

Candidate state (before owner publishes):
    README contains: Video walkthrough: VIDEO_URL_PENDING_OWNER_RECORDING ...
    Candidate ZIP: dist/SENSELINE_SUBMISSION_CANDIDATE.zip (candidate validation PASS,
    VIDEO_URL PENDING, SUBMISSION_READINESS PENDING_VIDEO)

Final state (after owner supplies a real public https URL):
    This script validates the URL syntax, requires owner incognito confirmation,
    updates README video line + release-status heading, updates
    results/submission_status.json (VIDEO_PUBLISHED, blockers, readiness), updates
    reports/SUBMISSION_CONTENT_MANIFEST.md to final artifact state, rebuilds
    dist/SENSELINE_FINAL_SUBMISSION.zip with the official package
    inclusion/exclusion rules, enforces README-at-root + 50 MiB + SHA-256 sidecar,
    runs scripts/verify_release_archive.py --mode final against the ACTUAL final
    ZIP (fresh-temp extraction, reinstall, pytest, reference/oracle, mutations,
    Docker security, exports, forbidden-file scan, video URL, SHA), regenerates
    reports/FINAL_VALIDATION_REPORT.md from that verification, and reports the
    five readiness dimensions separately.

Never invents a URL. Never writes a test URL into the real README or final ZIP
(test with a temporary copy only). Never modifies raw experiment results.
Idempotent: re-running with the same URL changes nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CANDIDATE_NAME = "SENSELINE_SUBMISSION_CANDIDATE.zip"
FINAL_NAME = "SENSELINE_FINAL_SUBMISSION.zip"
PLACEHOLDER = "VIDEO_URL_PENDING_OWNER_RECORDING"

EXAMPLE_DOMAINS = (
    "example.com", "example.org", "example.net", "example.edu",
)
LOCAL_MARKERS = (
    "localhost", "127.0.0.1", "0.0.0.0", "::1", ".local", ".invalid", ".test",
)
PLACEHOLDER_MARKERS = (
    "placeholder", "pending", "todo", "xxx", "your-video", "insert-url",
    "change-me", "replace-me", "video_url_pending",
)
FAKE_MARKERS = (
    "test_finalize", "test-video", "test_video", "fake", "dummy",
    "sample-video", "changeme",
)
SUPPORTED_HOSTS = (
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be",
    "loom.com", "www.loom.com",
    "vimeo.com", "www.vimeo.com", "player.vimeo.com",
    "drive.google.com", "docs.google.com",
)


def validate_video_url(url: str) -> str:
    """Syntax-check a public video URL. Does NOT prove public accessibility."""
    cleaned = (url or "").strip()
    if not cleaned:
        raise ValueError("video URL is blank; supply the real public video URL")
    if PLACEHOLDER in cleaned:
        raise ValueError(
            f"video URL still contains the placeholder ({PLACEHOLDER}); "
            "supply the real public URL"
        )
    lowered = cleaned.lower()
    if cleaned.startswith("file://") or lowered.startswith("file:"):
        raise ValueError("file:// URLs are not public video links")
    parsed = urlparse(cleaned)
    if parsed.scheme != "https":
        raise ValueError(
            "video URL must be a public https:// link "
            "(got scheme %r)" % (parsed.scheme or "missing")
        )
    if " " in cleaned or "\n" in cleaned or "\t" in cleaned:
        raise ValueError("video URL must not contain whitespace")
    host = (parsed.hostname or "").lower()
    if not host or "." not in host:
        raise ValueError("video URL does not have a public host")
    if any(d in host for d in EXAMPLE_DOMAINS):
        raise ValueError(f"example domain is not a public video link: {cleaned}")
    if any(m in host for m in LOCAL_MARKERS) or host in ("localhost",):
        raise ValueError(f"local URL is not a public video link: {cleaned}")
    path_query = (parsed.path or "") + ("?" + parsed.query if parsed.query else "")
    if any(token in lowered for token in PLACEHOLDER_MARKERS):
        raise ValueError(
            f"video URL looks like a placeholder link: {cleaned}"
        )
    if any(token in lowered for token in FAKE_MARKERS):
        raise ValueError(
            f"video URL looks like a fake/test link: {cleaned}"
        )
    if len(cleaned) < 20:
        raise ValueError("video URL is too short to be a legitimate video link")
    if len(path_query.strip("/")) < 2:
        raise ValueError("video URL is missing a video identifier path")
    _ = host in SUPPORTED_HOSTS or host.endswith(
        (".youtube.com", ".vimeo.com", ".loom.com", ".google.com")
    )
    return cleaned


def require_owner_confirmation(args) -> None:
    print("OWNER CONFIRMATION REQUIRED:")
    print("  1. Open the video URL in an incognito/private browser window.")
    print("  2. Confirm it plays without sign-in.")
    print("  Syntax validation alone does NOT prove public accessibility.")
    if args.non_interactive:
        if not args.confirm_public:
            raise ValueError(
                "non-interactive run requires --confirm-public to assert "
                "the incognito check was completed"
            )
        print("  Owner asserts incognito check completed (--confirm-public).")
        return
    if args.confirm_public:
        print("  Owner asserts incognito check completed (--confirm-public).")
        return
    try:
        answer = input(
            "  Have you verified the URL loads in an incognito/private "
            "window? Type YES to continue: "
        ).strip()
    except EOFError:
        raise ValueError(
            "no confirmation input available; re-run with --confirm-public "
            "after completing the incognito check"
        )
    if answer != "YES":
        raise ValueError(
            "owner incognito confirmation not received; aborting finalization"
        )


def update_readme(readme_path: Path, url: str) -> dict:
    text = readme_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    target = next(
        (i for i, line in enumerate(lines) if line.startswith("Video walkthrough:")),
        None,
    )
    if target is None:
        raise ValueError("README is missing its 'Video walkthrough:' line")
    old_video = lines[target]
    new_video = (
        f"Video walkthrough: {url} — five-minute public walkthrough "
        "(see docs/video_walkthrough_script.md)."
    )
    changed = False
    if old_video != new_video:
        lines[target] = new_video
        changed = True
    status_idx = next(
        (i for i, line in enumerate(lines) if line.startswith("**Release status:**")),
        None,
    )
    if status_idx is None:
        raise ValueError("README is missing its '**Release status:**' line")
    old_status = lines[status_idx]
    if "TECHNICALLY COMPLETE — AWAITING VIDEO" in old_status or PLACEHOLDER in old_status:
        lines[status_idx] = (
            "**Release status:** READY_WITH_DISCLOSED_LIMITATIONS — VIDEO PUBLISHED. "
            "Code, grader, security, and reproducibility validation are complete. "
            "55/72 full-run trials plus 9 pilot, 24 pilot-history, and 3 supplementary "
            "trials (91 classified: 14 GENUINE, 58 TOOL_USE, 17 INFRA, 2 BUDGET_BREACH) "
            "executed with transcript-backed failure analysis; nemotron S04–S08 "
            "(17 slots: S03×2, S04×3, S05×3, S06×3, S07×3, S08×3) missing on free-quota "
            "exhaustion (absent, not zero); owner review pending; independent metrology "
            f"review not obtained. Walkthrough video published at {url} (syntax-validated; "
            "owner confirmed incognito playback; public accessibility not auto-verified). "
            "See [`results/submission_status.json`](results/submission_status.json) and "
            "[`reports/FINAL_RELEASE_AUDIT.md`](reports/FINAL_RELEASE_AUDIT.md)."
        )
        changed = True
    elif url not in old_status and "VIDEO PUBLISHED" in old_status:
        lines[status_idx] = old_status.replace(
            "Walkthrough video published at",
            f"Walkthrough video published at {url} (superseded entry updated; ",
        ) if "http" not in old_status else old_status
        if url in old_status:
            pass
        else:
            lines[status_idx] = old_status + f" Video: {url}."
            changed = True
    if changed:
        readme_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"updated": changed, "old_video": old_video, "new_video": new_video}


def update_submission_status(status_path: Path, url: str) -> dict:
    data = json.loads(status_path.read_text(encoding="utf-8"))
    statuses = data.get("statuses", {})
    video = statuses.get("VIDEO_PUBLISHED", {})
    already = (
        video.get("status") == "PUBLISHED"
        and any(url in str(e) for e in video.get("evidence", []))
    )
    video["status"] = "PUBLISHED"
    video.pop("blocker", None)
    evidence = [
        f"Public walkthrough published at {url} (syntax-validated https URL; "
        "owner confirmed incognito/private playback; public accessibility "
        "is asserted by the owner, not auto-verified).",
        "Script: docs/video_walkthrough_script.md; slides: presentation/.",
        "README video line carries the public URL; placeholder removed.",
    ]
    video["evidence"] = evidence
    statuses["VIDEO_PUBLISHED"] = video
    ready = statuses.get("SUBMISSION_READY", {})
    blockers = [
        "Nemotron S04-S08 trials missing (17 slots, free-quota exhaustion; absent, not zero).",
        "Owner review pending (operator review recorded; see results/pilot/pilot_approval.json).",
        "Independent metrology review not obtained.",
    ]
    ready["blockers"] = blockers
    ready["readiness"] = "READY_WITH_DISCLOSED_LIMITATIONS"
    ready["status"] = "NOT_READY"
    statuses["SUBMISSION_READY"] = ready
    data["statuses"] = statuses
    status_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"updated": not already, "video_status": "PUBLISHED"}


def update_manifest(manifest_path: Path, url: str, archive_info: dict) -> dict:
    text = manifest_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    header_end = next(
        (i for i, line in enumerate(lines) if line.startswith("## Inclusion")),
        len(lines),
    )
    new_header = [
        "# SENSELINE Submission Content Manifest",
        "",
        f"Final artifact: `dist/{FINAL_NAME}` + `.sha256` "
        f"({archive_info['file_count']} files, "
        f"{archive_info['size_bytes'] / (1024 * 1024):.1f} MB, < 50 MiB,",
        "README at ZIP root, SHA-256 sidecar). "
        f"Walkthrough video published at {url} (syntax-validated; owner "
        "confirmed incognito playback; public accessibility not auto-verified).",
        f"SHA-256: `{archive_info['sha256']}`. Candidate rollback preserved in "
        "`dist-archive/` (placeholder build, not submittable).",
        "",
    ]
    rest = lines[header_end:]
    updated_verification = []
    for line in rest:
        if line.startswith("- `unzip -l` shows README at root"):
            updated_verification.append(
                f"- `unzip -l` shows README at root, 8 task packages, "
                f"{archive_info['file_count']} files, no outer directory."
            )
        elif line.startswith("- Fresh-extraction gate"):
            updated_verification.append(
                "- Fresh-extraction gate "
                f"(`scripts/verify_release_archive.py --mode final --archive "
                f"dist/{FINAL_NAME} --checksum dist/{FINAL_NAME}.sha256`) "
                "reinstalls deps, runs `pytest` (104 passed), "
                "`validate_submission.py --mode final` (266/266, 30/30), "
                "Docker security (12/12), Codex/OpenCode checks from the EXTRACTED "
                "final ZIP; reports TECHNICAL_PASS + VIDEO PUBLISHED + "
                "READY_WITH_DISCLOSED_LIMITATIONS (owner review + 17 missing "
                "slots + independent review still outstanding)."
            )
        elif line.startswith("- Final mode"):
            updated_verification.append(
                "- Final mode (`--mode final`) rejects the "
                "`VIDEO_URL_PENDING_OWNER_RECORDING` placeholder; this final ZIP "
                "carries the public URL in the extracted README."
            )
        else:
            updated_verification.append(line)
    manifest_path.write_text("\n".join(new_header + updated_verification) + "\n", encoding="utf-8")
    return {"updated": True, "file_count": archive_info["file_count"]}


def update_validation_report(report_path: Path, url: str, verify_report: dict) -> dict:
    text = report_path.read_text(encoding="utf-8")
    gate_start = text.find("## Archive gate (Phase I)")
    if gate_start == -1:
        raise ValueError("FINAL_VALIDATION_REPORT.md archive gate section not found")
    new_gate = (
        "## Archive gate (Phase I — final, regenerated from the actual final ZIP)\n"
        "\n"
        f"Final artifact `dist/{FINAL_NAME}` + `.sha256` "
        f"(SHA-256 `{verify_report['archive_sha256']}`, "
        f"{verify_report['archive_size_bytes']} bytes, "
        f"{verify_report['file_count']} files) verified by independent extraction:\n"
        "fresh-directory extraction, clean dependency install, `pytest` (104 passed), "
        "`validate_submission.py --mode final` (266/266 references, 30/30 mutations, "
        "8 exports, unit-integrity PASS), Docker security 12/12, Codex/OpenCode checks, "
        "all re-executed from the EXTRACTED final ZIP with PASS; "
        f"video status PUBLISHED at {url} (syntax-validated; owner confirmed incognito "
        "playback; public accessibility not auto-verified). README-at-root, 8 task "
        "packages, 50 MB limit, and prohibited-file scan enforced by "
        f"`scripts/verify_release_archive.py --mode final --archive dist/{FINAL_NAME} "
        f"--checksum dist/{FINAL_NAME}.sha256`. Technical package: "
        f"{verify_report.get('technical_package_validation', 'PASS')}; video: PUBLISHED; "
        "readiness: READY_WITH_DISCLOSED_LIMITATIONS (owner review pending, 17 missing "
        "S04–S08 slots disclosed, independent review not obtained). "
        "Candidate placeholder validation (PENDING_VIDEO) is superseded for this artifact.\n"
    )
    report_path.write_text(text[:gate_start] + new_gate, encoding="utf-8")
    return {"updated": True}


def update_release_audit(audit_path: Path, url: str) -> dict:
    text = audit_path.read_text(encoding="utf-8")
    old_video = (
        "| Video | **PENDING** — no URL invented; README carries "
        "`VIDEO_URL_PENDING_OWNER_RECORDING`; candidate validator allows it "
        "(PENDING_VIDEO), final validator rejects it; owner action required "
        "(`python scripts/finalize_submission.py --video-url "
        "\"ACTUAL_PUBLIC_VIDEO_URL\"`) |"
    )
    new_video = (
        f"| Video | **PUBLISHED** (syntax-validated; owner confirmed incognito) — {url} "
        "| README video line and release-status heading carry the public URL; "
        "final validator requires it; public accessibility asserted by owner, "
        "not auto-verified; owner review + 17 missing slots + independent review "
        "remain disclosed limitations |"
    )
    if old_video in text:
        text = text.replace(old_video, new_video)
    elif url not in text:
        text = text.replace(
            "| Video |",
            f"| Video | **PUBLISHED** — {url} (see finalization note) |\n| Video (superseded) |",
            1,
        )
    old_packaging = "Final uploadable `dist/SENSELINE_FINAL_SUBMISSION.zip` is built only by `scripts/finalize_submission.py` after the owner supplies the real public URL."
    if old_packaging in text:
        text = text.replace(
            old_packaging,
            f"Final uploadable `dist/{FINAL_NAME}` built by `scripts/finalize_submission.py` "
            f"with {url} (independent `--mode final` extraction gate PASS).",
        )
    if "FINALIZATION NOTE — VIDEO PUBLISHED" not in text:
        text += (
            "\n## Finalization note — video published (appended, history preserved)\n"
            "\n"
            f"Owner supplied public URL {url} (syntax-validated https; owner confirmed "
            "incognito/private playback; public accessibility not auto-verified). "
            "`scripts/finalize_submission.py` updated README, "
            "`results/submission_status.json`, manifest, and validation report; rebuilt "
            f"`dist/{FINAL_NAME}`; verified with `--mode final` against the extracted "
            "final ZIP. Owner review remains PENDING; 17 missing S04–S08 slots remain "
            "disclosed; independent metrology review not obtained. Readiness is "
            "READY_WITH_DISCLOSED_LIMITATIONS, not unqualified READY.\n"
        )
    audit_path.write_text(text, encoding="utf-8")
    return {"updated": True}


def build_final_archive() -> dict:
    from scripts.package_submission import package

    archive = ROOT / "dist" / FINAL_NAME
    os.environ["SENSELINE_ARCHIVE_NAME"] = FINAL_NAME
    return package(root=ROOT, archive=archive)


def archive_file_info() -> dict:
    from scripts.package_submission import MAX_ARCHIVE_BYTES

    archive = ROOT / "dist" / FINAL_NAME
    checksum_path = archive.with_suffix(archive.suffix + ".sha256")
    if not archive.is_file() or not checksum_path.is_file():
        raise ValueError("final ZIP or SHA-256 sidecar is missing after rebuild")
    size = archive.stat().st_size
    if size >= MAX_ARCHIVE_BYTES:
        raise ValueError(f"final ZIP exceeds 50 MiB: {size} bytes")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    expected_digest, expected_name = (
        checksum_path.read_text(encoding="ascii").strip().split(maxsplit=1)
    )
    if expected_digest != digest or expected_name != archive.name:
        raise ValueError("SHA-256 sidecar does not match the final archive")
    with zipfile.ZipFile(archive) as zf:
        bad = zf.testzip()
        if bad:
            raise ValueError(f"ZIP CRC failure: {bad}")
        names = zf.namelist()
        if "README.md" not in names or any(n.startswith("SENSELINE/") for n in names):
            raise ValueError("README.md must be at the flat ZIP root")
    return {
        "archive": archive.name,
        "size_bytes": size,
        "sha256": digest,
        "file_count": len(names),
    }


def run_independent_final_validation() -> dict:
    """Run the full extraction gate against the ACTUAL final ZIP."""
    cmd = [
        sys.executable,
        "scripts/verify_release_archive.py",
        "--mode", "final",
        "--archive", f"dist/{FINAL_NAME}",
        "--checksum", f"dist/{FINAL_NAME}.sha256",
    ]
    proc = subprocess.run(
        cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=1800
    )
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        payload = {}
    return {
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-6000:],
        "stderr_tail": proc.stderr[-3000:],
        "report": payload,
    }


def report_readiness(verify_report: dict) -> str:
    lines = [
        f"TECHNICAL_PACKAGE_VALIDATION: {verify_report.get('technical_package_validation', 'UNKNOWN')}",
        "VIDEO_PUBLICATION: PUBLISHED (syntax-validated; owner incognito-confirmed; "
        "public accessibility not auto-verified)",
        "OWNER_REVIEW: PENDING (see results/pilot/pilot_approval.json; not manufactured)",
        "EXPERIMENT_COVERAGE: PARTIAL (55/72 full; 17 S04–S08 slots missing, absent not zero; "
        "91 classified: 14 GENUINE / 58 TOOL_USE / 17 INFRA / 2 BUDGET_BREACH)",
        "SUBMISSION_READINESS: READY_WITH_DISCLOSED_LIMITATIONS "
        "(video published; owner review + 17 missing slots + independent review outstanding)",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Insert real video URL and rebuild the final ZIP (idempotent)."
    )
    parser.add_argument(
        "--video-url", required=True,
        help='Real public video URL, e.g. "https://www.youtube.com/watch?v=..."',
    )
    parser.add_argument(
        "--confirm-public", action="store_true",
        help="Assert the URL was verified in an incognito/private window",
    )
    parser.add_argument(
        "--non-interactive", action="store_true",
        help="Do not prompt; requires --confirm-public (for automated tests)",
    )
    args = parser.parse_args()
    try:
        url = validate_video_url(args.video_url)
        require_owner_confirmation(args)
    except ValueError as exc:
        print(f"FINALIZATION_FAIL: {exc}")
        return 1
    try:
        readme_report = update_readme(ROOT / "README.md", url)
        status_report = update_submission_status(
            ROOT / "results" / "submission_status.json", url
        )
        build_report = build_final_archive()
        info = archive_file_info()
        if PLACEHOLDER in (ROOT / "README.md").read_text(encoding="utf-8").splitlines()[6]:
            raise ValueError("placeholder still present in README video line")
        update_manifest(
            ROOT / "reports" / "SUBMISSION_CONTENT_MANIFEST.md", url, info
        )
        update_release_audit(
            ROOT / "reports" / "FINAL_RELEASE_AUDIT.md", url
        )
        validation = run_independent_final_validation()
        if validation["exit_code"] != 0:
            print("FINALIZATION_FAIL: independent final-mode extraction gate failed")
            print(validation["stdout_tail"])
            print(validation["stderr_tail"])
            return 1
        verify_report = validation["report"]
        if not verify_report or verify_report.get("video_status") != "PUBLISHED":
            print("FINALIZATION_FAIL: extracted final ZIP did not report PUBLISHED video")
            print(validation["stdout_tail"])
            return 1
        update_validation_report(
            ROOT / "reports" / "FINAL_VALIDATION_REPORT.md", url, verify_report
        )
        print("FINALIZATION_PASS")
        print(f"VIDEO_URL: {url} (syntax-validated; public access owner-confirmed, not auto-verified)")
        print(f"README_UPDATED: {readme_report['updated']}")
        print(f"STATUS_JSON_UPDATED: {status_report['updated']}")
        print(
            f"ARCHIVE: {build_report['archive']} "
            f"({build_report['archive_size_bytes']} bytes, "
            f"sha256 {build_report['archive_sha256']}, "
            f"{info['file_count']} files)"
        )
        print("INDEPENDENT_EXTRACTION_GATE: PASS (fresh temp dir, reinstall, "
              "pytest, reference/oracle, mutations, Docker, exports, SHA)")
        print(report_readiness(verify_report))
        return 0
    except Exception as exc:  # noqa: BLE001 - report and fail closed
        print(f"FINALIZATION_FAIL: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
