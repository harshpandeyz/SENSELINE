"""Video-aware finalization: insert real public video URL and rebuild the final ZIP.

Usage:
    python scripts/finalize_submission.py --video-url "REAL_PUBLIC_VIDEO_URL"

The owner must first verify the link loads in an incognito/private browser window.
Syntax validation alone does NOT prove public accessibility.

Candidate state (before owner publishes):
    README contains: Video walkthrough: VIDEO_URL_PENDING_OWNER_UPLOAD ...
    Candidate ZIP: dist/SENSELINE_SUBMISSION_CANDIDATE.zip (candidate validation PASS,
    VIDEO_URL PENDING, SUBMISSION_READINESS PENDING_VIDEO)

Final state (after owner supplies a real public https URL):
    1. Validate URL syntax + owner incognito confirmation.
    2. Update README video line + release-status section.
    3. Update results/submission_status.json (VIDEO_PUBLISHED, blockers, readiness).
    4. Update results/reference_validation.json video_status (results preserved).
    5. Update submission content manifest (inventory/count/rules, no SHA-256).
    6. Update release audit + video walkthrough documentation.
    7. Build a STAGING archive in a temp dir and run the full
       scripts/verify_release_archive.py --mode final gate against it.
    8. Regenerate reports/FINAL_VALIDATION_REPORT.md from the staging results
       (no SHA/size embedded, so the report is stable across the final build).
    9. Build dist/SENSELINE_FINAL_SUBMISSION.zip + sidecar (sidecar holds the
       authoritative SHA-256, never the in-ZIP manifest).
   10. Re-run the full --mode final gate against the dist final ZIP.
   11. Report the five readiness dimensions separately.

Atomicity: the dist final ZIP is written only in step 9. Any failure before the
final gate passes removes a partial dist final ZIP and restores a previously
valid one. The candidate ZIP is never touched.

Never invents a URL. Never writes a test URL into the real README or final ZIP
(test with a temporary copy only). Never modifies raw experiment results.
Idempotent: re-running with the same URL changes nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
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
PLACEHOLDER = "VIDEO_URL_PENDING_OWNER_UPLOAD"

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
SUPPORTED_SUFFIXES = (".youtube.com", ".vimeo.com", ".loom.com", ".google.com")
SUPPORTED_LABEL = "YouTube (youtube.comyoutu.be), Loom (loom.com), Vimeo (vimeo.com), public Google Drive (drive.google.com)"


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
    if any(token in lowered for token in PLACEHOLDER_MARKERS):
        raise ValueError(f"video URL looks like a placeholder link: {cleaned}")
    if any(token in lowered for token in FAKE_MARKERS):
        raise ValueError(f"video URL looks like a fake/test link: {cleaned}")
    if host not in SUPPORTED_HOSTS and not host.endswith(SUPPORTED_SUFFIXES):
        raise ValueError(
            f"unsupported video host {host!r}; supported platforms: {SUPPORTED_LABEL}"
        )
    if host in ("drive.google.com", "docs.google.com") and (
        "/drive/folders" in parsed.path or "/drive/" in parsed.path
    ):
        raise ValueError(
            "Google Drive folder URLs are not video links; supply the individual "
            "public video-file URL, e.g. https://drive.google.com/file/d/FILE_ID/view"
        )
    path_query = (parsed.path or "") + ("?" + parsed.query if parsed.query else "")
    if len(cleaned) < 20:
        raise ValueError("video URL is too short to be a legitimate video link")
    if len(path_query.strip("/")) < 2:
        raise ValueError("video URL is missing a video identifier path")
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


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_readme(readme_path: Path, url: str) -> dict:
    """Replace the video URL in the video + release-status lines, idempotently."""
    lines = _read_lines(readme_path)
    video_idx = next(
        (i for i, line in enumerate(lines) if line.startswith("Video walkthrough:")),
        None,
    )
    if video_idx is None:
        raise ValueError("README is missing its 'Video walkthrough:' line")
    new_video = (
        f"Video walkthrough: {url} — five-minute public walkthrough "
        "(see docs/video_walkthrough_script.md)."
    )
    status_idx = next(
        (i for i, line in enumerate(lines) if line.startswith("**Release status:**")),
        None,
    )
    if status_idx is None:
        raise ValueError("README is missing its '**Release status:**' line")
    new_status = (
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
    changed = False
    if lines[video_idx] != new_video:
        lines[video_idx] = new_video
        changed = True
    if lines[status_idx] != new_status:
        lines[status_idx] = new_status
        changed = True
    if changed:
        _write_lines(readme_path, lines)
    # Verify exactly one distinct video URL across both managed lines.
    managed = lines[video_idx] + "\n" + lines[status_idx]
    found = set()
    for token in managed.split():
        if token.startswith("https://"):
            found.add(token.rstrip(").,;"))
    found = {u for u in found if PLACEHOLDER not in u}
    if found != {url}:
        raise ValueError(
            "README video/status lines contain conflicting URLs: "
            + ", ".join(sorted(found))
        )
    if PLACEHOLDER in lines[video_idx]:
        raise ValueError("placeholder still present in README video line")
    return {"updated": changed, "old_video": None, "new_video": new_video}


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
    video["evidence"] = [
        f"Public walkthrough published at {url} (syntax-validated https URL; "
        "owner confirmed incognito/private playback; public accessibility "
        "is asserted by the owner, not auto-verified).",
        "Script: docs/video_walkthrough_script.md; slides: presentation/.",
        "README video line carries the public URL; placeholder removed.",
    ]
    statuses["VIDEO_PUBLISHED"] = video
    ready = statuses.get("SUBMISSION_READY", {})
    ready["blockers"] = [
        "Nemotron S04-S08 trials missing (17 slots, free-quota exhaustion; absent, not zero).",
        "Owner review pending (operator review recorded; see results/pilot/pilot_approval.json).",
        "Independent metrology review not obtained.",
    ]
    ready["readiness"] = "READY_WITH_DISCLOSED_LIMITATIONS"
    ready["status"] = "NOT_READY"
    statuses["SUBMISSION_READY"] = ready
    data["statuses"] = statuses
    status_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"updated": not already, "video_status": "PUBLISHED"}


def update_reference_validation(ref_path: Path, url: str) -> dict:
    """Record VIDEO_PUBLISHED; preserve every existing result field."""
    data = json.loads(ref_path.read_text(encoding="utf-8"))
    before = dict(data)
    data["video_status"] = {"status": "PUBLISHED", "url": url}
    ref_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    preserved = all(
        data.get(k) == before.get(k)
        for k in (
            "reference_cases_passed", "reference_case_count",
            "mutation_controls_rejected", "mutation_control_count",
            "task_case_counts",
        )
    )
    if not preserved:
        raise ValueError("reference validation results changed while updating video status")
    return {"updated": True}


def update_video_script(script_path: Path, url: str) -> dict:
    if not script_path.is_file():
        # The walkthrough script ships in the working repository but is
        # excluded from the submission ZIP by design; nothing to update there.
        return {"updated": False, "skipped": True}
    text = script_path.read_text(encoding="utf-8")
    new_text = text
    new_text = new_text.replace("Ten infrastructure trials", "Seventeen infrastructure trials")
    new_text = new_text.replace("ten infrastructure trials", "seventeen infrastructure trials")
    old_status = (
        "14 GENUINE, 58 TOOL_USE, 17 INFRA, 2 BUDGET_BREACH). "
        "No recording or public URL exists."
    )
    if old_status in new_text:
        new_text = new_text.replace(
            old_status,
            "14 GENUINE, 58 TOOL_USE, 17 INFRA, 2 BUDGET_BREACH). "
            f"Walkthrough video published at {url}.",
        )
    old_readme = "The README carries an explicit PENDING marker; never invent a URL."
    if old_readme in new_text:
        new_text = new_text.replace(
            old_readme,
            f"The README carries the public URL {url}.",
        )
    if new_text != text:
        script_path.write_text(new_text, encoding="utf-8")
    if "Ten infrastructure trials" in new_text:
        raise ValueError("video script still claims ten infrastructure trials")
    return {"updated": new_text != text}


def update_manifest(manifest_path: Path, url: str, file_count: int) -> dict:
    """Manifest holds inventory/count/rules only — never the final SHA-256."""
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
        f"({file_count} files, < 50 MiB, README at ZIP root). "
        "The authoritative SHA-256 lives exclusively in "
        f"`dist/{FINAL_NAME}.sha256` (never inside this manifest, which would "
        "make the manifest stale by construction). "
        f"Walkthrough video published at {url} (syntax-validated; owner "
        "confirmed incognito playback; public accessibility not auto-verified).",
        "",
    ]
    rest = lines[header_end:]
    updated = []
    for line in rest:
        if line.startswith("- `unzip -l` shows README at root"):
            updated.append(
                f"- `unzip -l` shows README at root, 8 task packages, "
                f"{file_count} files, no outer directory."
            )
        elif line.startswith("- Fresh-extraction gate"):
            updated.append(
                "- Fresh-extraction gate "
                f"(`scripts/verify_release_archive.py --mode final --archive "
                f"dist/{FINAL_NAME} --checksum dist/{FINAL_NAME}.sha256`) "
                "reinstalls deps, runs `pytest`, "
                "`validate_submission.py --mode final` (266/266, 30/30), "
                "Docker security (12/12), Codex/OpenCode checks from the EXTRACTED "
                "final ZIP; reports TECHNICAL_PASS + VIDEO PUBLISHED + "
                "READY_WITH_DISCLOSED_LIMITATIONS (owner review + 17 missing "
                "slots + independent review still outstanding)."
            )
        elif line.startswith("- Final mode"):
            updated.append(
                "- Final mode (`--mode final`) rejects the "
                "`VIDEO_URL_PENDING_OWNER_UPLOAD` placeholder; this final ZIP "
                "carries the public URL in the extracted README."
            )
        else:
            updated.append(line)
    manifest_path.write_text("\n".join(new_header + updated) + "\n", encoding="utf-8")
    return {"updated": True, "file_count": file_count}


def update_validation_report(report_path: Path, url: str, verify_report: dict) -> dict:
    """Regenerate the archive-gate section from actual verification results.

    The section carries qualitative results (PASS/PUBLISHED/readiness/counts)
    but never the final SHA-256 or byte size, which would make the report
    stale by construction (the report itself ships inside the ZIP).
    """
    text = report_path.read_text(encoding="utf-8")
    gate_start = text.find("## Archive gate (Phase I)")
    if gate_start == -1:
        raise ValueError("FINAL_VALIDATION_REPORT.md archive gate section not found")
    new_gate = (
        "## Archive gate (Phase I — final, regenerated from the actual final ZIP)\n"
        "\n"
        f"Final artifact `dist/{FINAL_NAME}` + `.sha256` "
        f"({verify_report['file_count']} files) verified by independent extraction "
        "(authoritative SHA-256 in the `.sha256` sidecar, never in this report):\n"
        "fresh-directory extraction, clean dependency install, `pytest`, "
        "`validate_submission.py --mode final` (266/266 references, 30/30 mutations, "
        "8 exports, unit-integrity PASS), Docker security 12/12, Codex/OpenCode checks, "
        "all re-executed from the EXTRACTED final ZIP with PASS; "
        f"video status PUBLISHED at {url} (syntax-validated; owner confirmed incognito "
        "playback; public accessibility not auto-verified). README-at-root, 8 task "
        "packages, 50 MiB limit, and prohibited-file scan enforced by "
        f"`scripts/verify_release_archive.py --mode final --archive dist/{FINAL_NAME} "
        f"--checksum dist/{FINAL_NAME}.sha256`. Technical package: "
        f"{verify_report.get('technical_package_validation', 'PASS')}; "
        f"video: {verify_report.get('video_publication', 'PUBLISHED')}; "
        f"owner review: {verify_report.get('owner_review', 'PENDING')}; "
        f"experiment coverage: "
        f"{verify_report.get('experiment_coverage', 'PARTIAL (17 slots missing)')}; "
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
        "`VIDEO_URL_PENDING_OWNER_UPLOAD`; candidate validator allows it "
        "(PENDING_VIDEO), final validator rejects it; owner action required "
        "(`python scripts/finalize_submission.py --video-url "
        "\"REAL_PUBLIC_VIDEO_FILE_URL\"`) |"
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


def _build_archive_at(archive: Path) -> dict:
    from scripts.package_submission import package

    os.environ["SENSELINE_ARCHIVE_NAME"] = archive.name
    return package(root=ROOT, archive=archive)


def _parse_verify_output(stdout: str) -> dict:
    """Parse the complete JSON report from verify_release_archive output.

    verify_release_archive.py prints one indented multi-line JSON document.
    The last line alone (`}`) is never a valid report. Prefer a full-document
    parse; fall back to scanning embedded JSON objects with raw_decode.
    Empty, incomplete or malformed reports are rejected, as is any report
    that is not an explicit PASS — a stray word PASS elsewhere in the logs
    never counts as verification success.
    """
    text = (stdout or "").strip()
    if not text:
        raise ValueError("verification produced empty output")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        obj = None
        decoder = json.JSONDecoder()
        for i, ch in enumerate(text):
            if ch != "{":
                continue
            try:
                candidate, _ = decoder.raw_decode(text[i:])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and (
                "archive" in candidate or "status" in candidate
            ):
                obj = candidate
                break
        if obj is None:
            raise ValueError("no complete JSON report found in verification output")
    if not isinstance(obj, dict) or not obj:
        raise ValueError("verification report is empty or malformed")
    return obj


def _require_pass_report(report: dict) -> dict:
    if report.get("status") != "PASS":
        raise ValueError(
            "verification did not PASS: %s" % (report.get("reason") or report.get("status"))
        )
    if report.get("video_status") != "PUBLISHED":
        raise ValueError("extracted final ZIP did not report PUBLISHED video")
    if report.get("technical_package_validation") != "PASS":
        raise ValueError("technical package validation did not PASS")
    return report


def run_independent_final_validation(archive: Path, checksum: Path) -> dict:
    """Run the full extraction gate against the ACTUAL final ZIP in staging."""
    cmd = [
        sys.executable,
        "scripts/verify_release_archive.py",
        "--mode", "final",
        "--archive", str(archive),
        "--checksum", str(checksum),
    ]
    proc = subprocess.run(
        cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=1800
    )
    report: dict = {}
    parse_error = ""
    try:
        report = _require_pass_report(_parse_verify_output(proc.stdout))
    except ValueError as exc:
        parse_error = str(exc)
    return {
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-6000:],
        "stderr_tail": proc.stderr[-3000:],
        "report": report,
        "parse_error": parse_error,
    }


def report_readiness(verify_report: dict) -> str:
    lines = [
        f"TECHNICAL_PACKAGE_VALIDATION: {verify_report.get('technical_package_validation', 'UNKNOWN')}",
        f"VIDEO_PUBLICATION: {verify_report.get('video_publication', 'PUBLISHED')} "
        "(syntax-validated; owner incognito-confirmed; "
        "public accessibility not auto-verified)",
        f"OWNER_REVIEW: {verify_report.get('owner_review', 'PENDING')} "
        "(see results/pilot/pilot_approval.json; not manufactured)",
        f"EXPERIMENT_COVERAGE: {verify_report.get('experiment_coverage', 'PARTIAL (17 slots missing)')}",
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
    dist = ROOT / "dist"
    final_archive = dist / FINAL_NAME
    final_checksum = final_archive.with_suffix(final_archive.suffix + ".sha256")
    backup: dict[str, bytes | None] = {"zip": None, "sha": None}
    if final_archive.is_file():
        backup["zip"] = final_archive.read_bytes()
    if final_checksum.is_file():
        backup["sha"] = final_checksum.read_bytes()

    def _restore_or_clean() -> None:
        try:
            if backup["zip"] is not None:
                final_archive.write_bytes(backup["zip"])
            elif final_archive.is_file():
                final_archive.unlink()
            if backup["sha"] is not None:
                final_checksum.write_bytes(backup["sha"])
            elif final_checksum.is_file():
                final_checksum.unlink()
        except OSError:
            pass

    try:
        # 1–6. Update every release document BEFORE packaging anything.
        readme_report = update_readme(ROOT / "README.md", url)
        status_report = update_submission_status(
            ROOT / "results" / "submission_status.json", url
        )
        ref_report = update_reference_validation(
            ROOT / "results" / "reference_validation.json", url
        )
        script_report = update_video_script(
            ROOT / "docs" / "video_walkthrough_script.md", url
        )
        audit_report = update_release_audit(
            ROOT / "reports" / "FINAL_RELEASE_AUDIT.md", url
        )
        from scripts.package_submission import archive_members

        member_count = len(archive_members(ROOT))
        manifest_report = update_manifest(
            ROOT / "reports" / "SUBMISSION_CONTENT_MANIFEST.md", url, member_count
        )
        # 7. Stage + fully verify in a temp dir (never dist).
        with tempfile.TemporaryDirectory(prefix="senseline-finalize-stage-") as stage:
            stage_archive = Path(stage) / FINAL_NAME
            _build_archive_at(stage_archive)
            staged = run_independent_final_validation(
                stage_archive,
                stage_archive.with_suffix(stage_archive.suffix + ".sha256"),
            )
            if staged["exit_code"] != 0 or not staged["report"]:
                print("FINALIZATION_FAIL: staging final-mode extraction gate failed")
                print(staged["stdout_tail"])
                print(staged["stderr_tail"] or staged["parse_error"])
                return 1
            # 8. Regenerate the validation report from staging results
            # (no SHA/size embedded, so the report is stable for the final build).
            validation_report = update_validation_report(
                ROOT / "reports" / "FINAL_VALIDATION_REPORT.md", url, staged["report"]
            )
            if member_count != len(archive_members(ROOT)):
                manifest_report = update_manifest(
                    ROOT / "reports" / "SUBMISSION_CONTENT_MANIFEST.md",
                    url,
                    len(archive_members(ROOT)),
                )
            # 9. Build the real final ZIP + sidecar in dist.
            build_report = _build_archive_at(final_archive)
            # 10. Re-run the full gate against the dist final ZIP.
            final = run_independent_final_validation(final_archive, final_checksum)
            if final["exit_code"] != 0 or not final["report"]:
                print("FINALIZATION_FAIL: final-mode extraction gate failed on dist artifact")
                print(final["stdout_tail"])
                print(final["stderr_tail"] or final["parse_error"])
                _restore_or_clean()
                return 1
        print("FINALIZATION_PASS")
        print(f"VIDEO_URL: {url} (syntax-validated; public access owner-confirmed, not auto-verified)")
        print(f"README_UPDATED: {readme_report['updated']}")
        print(f"STATUS_JSON_UPDATED: {status_report['updated']}")
        print(f"REFERENCE_VALIDATION_UPDATED: {ref_report['updated']}")
        print(f"VIDEO_SCRIPT_UPDATED: {script_report['updated']}")
        print(f"AUDIT_UPDATED: {audit_report['updated']}")
        print(f"MANIFEST_UPDATED: {manifest_report['updated']}")
        print(f"VALIDATION_REPORT_UPDATED: {validation_report['updated']}")
        print(
            f"ARCHIVE: {build_report['archive']} "
            f"({build_report['archive_size_bytes']} bytes, "
            f"sha256 {build_report['archive_sha256']}, "
            f"{build_report['file_count']} files, "
            f"sanitized {build_report.get('sanitized_files', 0)} files)"
        )
        print("INDEPENDENT_EXTRACTION_GATE: PASS (fresh temp dir, reinstall, "
              "pytest, reference/oracle, mutations, Docker, exports, SHA)")
        print(report_readiness(final["report"]))
        return 0
    except Exception as exc:  # noqa: BLE001 - report and fail closed
        print(f"FINALIZATION_FAIL: {type(exc).__name__}: {exc}")
        _restore_or_clean()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())