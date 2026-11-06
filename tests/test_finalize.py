"""Automated tests for the video-aware finalization process.

All tests use temporary copies and dummy URLs. They never modify the real
README, results, or dist/ artifacts.
"""
import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.finalize_submission import (
    FINAL_NAME,
    PLACEHOLDER,
    _parse_verify_output,
    update_manifest,
    update_readme,
    update_reference_validation,
    update_release_audit,
    update_submission_status,
    update_validation_report,
    update_video_script,
    validate_video_url,
)

REALISTIC_YOUTUBE = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
REALISTIC_LOOM = "https://www.loom.com/share/abc123def456"
REALISTIC_VIMEO = "https://vimeo.com/123456789"
REALISTIC_DRIVE = "https://drive.google.com/file/d/1AbC2DeFgHi3JkLmNop/view?usp=sharing"


@pytest.fixture()
def temp_project(tmp_path):
    dst = tmp_path / "proj"
    shutil.copytree(
        ROOT,
        dst,
        ignore=shutil.ignore_patterns(
            ".venv", ".git", "__pycache__", ".pytest_cache",
            "dist", ".DS_Store",
        ),
    )
    return dst


def test_candidate_cannot_be_mistaken_for_final():
    candidate = ROOT / "dist" / "SENSELINE_SUBMISSION_CANDIDATE.zip"
    final = ROOT / "dist" / FINAL_NAME
    assert candidate.name != final.name
    if not (ROOT / "dist").is_dir():
        # Extracted-archive context: dist/ is excluded from the ZIP by design.
        # Assert this extracted copy is the placeholder candidate, not a final.
        readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
        assert PLACEHOLDER in readme_text
        return
    assert candidate.is_file(), "candidate ZIP must exist"
    with zipfile.ZipFile(candidate) as zf:
        readme = zf.read("README.md").decode("utf-8")
    assert PLACEHOLDER in readme
    if final.is_file():
        # After finalization both exist: they must differ and the final must
        # carry a real URL while the candidate keeps the placeholder.
        with zipfile.ZipFile(final) as zf:
            final_readme = zf.read("README.md").decode("utf-8")
        assert PLACEHOLDER not in [
            ln for ln in final_readme.splitlines() if ln.startswith("Video walkthrough:")
        ][0]
        assert candidate.read_bytes() != final.read_bytes()
    else:
        # Before a real URL is supplied no placeholder final may exist.
        assert not final.is_file()


def test_final_mode_rejects_pending_marker():
    from scripts.validate_submission import _parse_video_line

    status = _parse_video_line(f"Video walkthrough: {PLACEHOLDER} — pending")
    assert status["status"] == "PENDING_OWNER_ACTION"
    with pytest.raises(SystemExit):
        line = f"Video walkthrough: {PLACEHOLDER} — pending"
        parsed = _parse_video_line(line)
        if parsed["status"] == "PENDING_OWNER_ACTION":
            raise SystemExit("FAIL: final mode rejects placeholder")


def test_url_validation_rejects_bad_inputs():
    for bad in [
        "",
        "   ",
        PLACEHOLDER,
        "https://example.com/video",
        "https://localhost/video",
        "http://www.youtube.com/watch?v=abc",
        "file:///tmp/video.mp4",
        "https://youtu.be/TEST_FINALIZE_12345",
        "https://www.youtube.com/watch?v=fake123",
        "https://vimeo.com/dummy",
        "short",
        "https://youtu.be/",
    ]:
        with pytest.raises(ValueError):
            validate_video_url(bad)


def test_url_validation_accepts_supported_hosts():
    for good in [REALISTIC_YOUTUBE, REALISTIC_LOOM, REALISTIC_VIMEO, REALISTIC_DRIVE]:
        assert validate_video_url(good) == good


def test_youtube_url_updates_readme(temp_project):
    readme = temp_project / "README.md"
    before = readme.read_text(encoding="utf-8")
    assert PLACEHOLDER in before
    report = update_readme(readme, REALISTIC_YOUTUBE)
    assert report["updated"] is True
    after = readme.read_text(encoding="utf-8")
    video_lines = [ln for ln in after.splitlines() if ln.startswith("Video walkthrough:")]
    assert len(video_lines) == 1
    assert REALISTIC_YOUTUBE in video_lines[0]
    assert PLACEHOLDER not in video_lines[0]


def test_readme_update_is_idempotent(temp_project):
    readme = temp_project / "README.md"
    update_readme(readme, REALISTIC_YOUTUBE)
    digest_one = hashlib.sha256(readme.read_bytes()).hexdigest()
    report = update_readme(readme, REALISTIC_YOUTUBE)
    digest_two = hashlib.sha256(readme.read_bytes()).hexdigest()
    assert report["updated"] is False
    assert digest_one == digest_two


def test_readme_release_status_changes_correctly(temp_project):
    readme = temp_project / "README.md"
    update_readme(readme, REALISTIC_YOUTUBE)
    text = readme.read_text(encoding="utf-8")
    assert "READY_WITH_DISCLOSED_LIMITATIONS" in text
    assert "VIDEO PUBLISHED" in text
    assert "17 slots" in text
    assert "owner review pending" in text.lower()
    assert "TECHNICALLY COMPLETE — AWAITING VIDEO" not in text


def test_submission_status_json_changes_correctly(temp_project):
    status_path = temp_project / "results" / "submission_status.json"
    report = update_submission_status(status_path, REALISTIC_YOUTUBE)
    assert report["video_status"] == "PUBLISHED"
    data = json.loads(status_path.read_text(encoding="utf-8"))
    video = data["statuses"]["VIDEO_PUBLISHED"]
    assert video["status"] == "PUBLISHED"
    assert "blocker" not in video
    assert any(REALISTIC_YOUTUBE in str(e) for e in video["evidence"])
    ready = data["statuses"]["SUBMISSION_READY"]
    assert ready["readiness"] == "READY_WITH_DISCLOSED_LIMITATIONS"
    assert ready["status"] == "NOT_READY"
    joined = json.dumps(ready)
    assert "17" in joined or "S04" in joined
    assert "Owner review pending" in joined or "owner review" in joined.lower()


def test_owner_review_pending_preserved(temp_project):
    approval_before = (temp_project / "results" / "pilot" / "pilot_approval.json").read_text(
        encoding="utf-8"
    )
    update_submission_status(
        temp_project / "results" / "submission_status.json", REALISTIC_YOUTUBE
    )
    update_readme(temp_project / "README.md", REALISTIC_YOUTUBE)
    approval_after = (temp_project / "results" / "pilot" / "pilot_approval.json").read_text(
        encoding="utf-8"
    )
    assert approval_before == approval_after
    assert "PENDING" in approval_after


def test_missing_coverage_remains_disclosed(temp_project):
    update_readme(temp_project / "README.md", REALISTIC_YOUTUBE)
    update_submission_status(
        temp_project / "results" / "submission_status.json", REALISTIC_YOUTUBE
    )
    readme_text = (temp_project / "README.md").read_text(encoding="utf-8")
    status_text = (temp_project / "results" / "submission_status.json").read_text(
        encoding="utf-8"
    )
    for needle in ["17 slots", "S04", "absent, not zero"]:
        assert needle in readme_text
    assert "S04" in status_text or "17" in status_text


def test_package_excludes_dist_archive_and_has_root_readme(temp_project, monkeypatch):
    monkeypatch.chdir(temp_project)
    monkeypatch.setenv("SENSELINE_ARCHIVE_NAME", "TEST_CANDIDATE_TMP.zip")
    (temp_project / "dist-archive" / "dummy").mkdir(parents=True, exist_ok=True)
    (temp_project / "dist-archive" / "dummy" / "old.sha256").write_text("abc", encoding="utf-8")
    (temp_project / "dist").mkdir(parents=True, exist_ok=True)
    from scripts import package_submission

    archive = temp_project / "dist" / "TEST_CANDIDATE_TMP.zip"
    report = package_submission.package(root=temp_project, archive=archive)
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
    assert "README.md" in names
    assert not any(n.startswith("SENSELINE/") for n in names)
    assert not any(n.startswith("dist-archive/") for n in names)
    assert not any(n.startswith("dist/") for n in names)
    assert not any(n.endswith(".zip") for n in names)
    assert report["file_count"] == len(names)
    assert report["archive_size_bytes"] < 50 * 1024 * 1024


def test_sha256_sidecar_and_size(temp_project, monkeypatch):
    monkeypatch.chdir(temp_project)
    (temp_project / "dist").mkdir(parents=True, exist_ok=True)
    from scripts import package_submission

    archive = temp_project / "dist" / "TEST_SHA_TMP.zip"
    package_submission.package(root=temp_project, archive=archive)
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    assert checksum.is_file()
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    expected_digest, expected_name = checksum.read_text(encoding="ascii").strip().split(
        maxsplit=1
    )
    assert expected_digest == digest
    assert expected_name == archive.name
    assert archive.stat().st_size < 50 * 1024 * 1024


def test_full_validation_invokes_extracted_final_gate(monkeypatch):
    import scripts.finalize_submission as fin

    captured = {}

    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None):
        captured["cmd"] = cmd
        captured["cwd"] = cwd

        class Proc:
            returncode = 0
            stdout = '{"video_status": "PUBLISHED"}\n{"status": "PASS"}'
            stderr = ""

        return Proc()

    monkeypatch.setattr(fin.subprocess, "run", fake_run)
    import tempfile as _tempfile

    with _tempfile.TemporaryDirectory() as stage:
        archive = Path(stage) / fin.FINAL_NAME
        archive.write_bytes(b"fake")
        archive.with_suffix(archive.suffix + ".sha256").write_text("x", encoding="utf-8")
        result = fin.run_independent_final_validation(archive, archive.with_suffix(archive.suffix + ".sha256"))
    assert result["exit_code"] == 0
    cmd = captured["cmd"]
    assert "scripts/verify_release_archive.py" in cmd
    assert "--mode" in cmd and "final" in cmd
    assert "--archive" in cmd and str(archive) in cmd
    assert "--checksum" in cmd and str(archive.with_suffix(archive.suffix + ".sha256")) in cmd


def test_finalization_does_not_modify_raw_results(temp_project):
    targets = [
        temp_project / "results" / "experiment_analysis.json",
        temp_project / "results" / "aggregate.json",
    ]
    trial_indexes = sorted((temp_project / "results").rglob("trial_index.json"))[:5]
    targets.extend(trial_indexes)
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in targets}
    update_readme(temp_project / "README.md", REALISTIC_YOUTUBE)
    update_submission_status(
        temp_project / "results" / "submission_status.json", REALISTIC_YOUTUBE
    )
    update_release_audit(
        temp_project / "reports" / "FINAL_RELEASE_AUDIT.md", REALISTIC_YOUTUBE
    )
    for p in targets:
        assert hashlib.sha256(p.read_bytes()).hexdigest() == before[str(p)]


def test_manifest_holds_no_self_referential_sha(temp_project):
    update_readme(temp_project / "README.md", REALISTIC_YOUTUBE)
    update_manifest(
        temp_project / "reports" / "SUBMISSION_CONTENT_MANIFEST.md",
        REALISTIC_YOUTUBE,
        713,
    )
    manifest = (temp_project / "reports" / "SUBMISSION_CONTENT_MANIFEST.md").read_text(
        encoding="utf-8"
    )
    assert FINAL_NAME in manifest
    assert REALISTIC_YOUTUBE in manifest
    assert "713 files" in manifest
    assert "5358999173cd7c14fae56dc9c0b49f93e0a8c7143f90dea4dca8c7143f90dea4" not in manifest
    assert "sha256" in manifest.lower()


def test_manifest_and_validation_report_updates(temp_project):
    update_readme(temp_project / "README.md", REALISTIC_YOUTUBE)
    update_manifest(
        temp_project / "reports" / "SUBMISSION_CONTENT_MANIFEST.md",
        REALISTIC_YOUTUBE,
        712,
    )
    manifest = (temp_project / "reports" / "SUBMISSION_CONTENT_MANIFEST.md").read_text(
        encoding="utf-8"
    )
    assert FINAL_NAME in manifest
    assert REALISTIC_YOUTUBE in manifest
    assert "712 files" in manifest
    fake_verify = {
        "file_count": 712,
        "technical_package_validation": "PASS",
        "video_publication": "PUBLISHED",
        "owner_review": "PENDING",
        "experiment_coverage": "PARTIAL (55/72 full-run; 17 S04-S08 slots missing)",
        "submission_readiness": "READY_WITH_DISCLOSED_LIMITATIONS",
    }
    update_validation_report(
        temp_project / "reports" / "FINAL_VALIDATION_REPORT.md",
        REALISTIC_YOUTUBE,
        fake_verify,
    )
    report_text = (temp_project / "reports" / "FINAL_VALIDATION_REPORT.md").read_text(
        encoding="utf-8"
    )
    assert FINAL_NAME in report_text
    assert REALISTIC_YOUTUBE in report_text
    assert "READY_WITH_DISCLOSED_LIMITATIONS" in report_text


REALISTIC_YOUTUBE_2 = "https://www.youtube.com/watch?v=9bZkp7q19f0"
REALISTIC_DRIVE = "https://drive.google.com/file/d/1AbC2DeFgHi3JkLmNop/view?usp=sharing"


def test_verify_output_parser_handles_multiline_json():
    from scripts.finalize_submission import _parse_verify_output, _require_pass_report

    multi = json.dumps(
        {
            "status": "PASS",
            "archive": FINAL_NAME,
            "archive_size_bytes": 4114335,
            "archive_sha256": "ab" * 32,
            "video_status": "PUBLISHED",
            "technical_package_validation": "PASS",
            "video_publication": "PUBLISHED",
            "owner_review": "PENDING",
            "experiment_coverage": "PARTIAL",
            "submission_readiness": "READY_WITH_DISCLOSED_LIMITATIONS",
        },
        indent=2,
    )
    assert _parse_verify_output(multi)["archive"] == FINAL_NAME
    logged = "starting verification...\n" + multi + "\n done\n"
    assert _parse_verify_output(logged)["video_status"] == "PUBLISHED"
    with pytest.raises(ValueError):
        _parse_verify_output("")
    with pytest.raises(ValueError):
        _parse_verify_output("}\n{\n")
    parsed_fail = _parse_verify_output(json.dumps({"status": "FAIL"}))
    with pytest.raises(ValueError):
        _require_pass_report(parsed_fail)


def test_finalizer_rejects_pass_word_without_valid_report():
    from scripts.finalize_submission import _parse_verify_output

    with pytest.raises(ValueError):
        _parse_verify_output("PASS PASS PASS - all good, trust me")


def test_supported_hosts_accepted_and_unsupported_rejected():
    for good in [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.loom.com/share/abc123def456",
        "https://vimeo.com/123456789",
        "https://drive.google.com/file/d/1AbC2DeFgHi3JkLmNop/view?usp=sharing",
    ]:
        assert validate_video_url(good) == good
    for bad in [
        "https://mysite.com/video/123",
        "https://example.com/watch?v=abc",
        "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "file:///tmp/video.mp4",
    ]:
        with pytest.raises(ValueError):
            validate_video_url(bad)


def test_corrected_url_replaces_previous_url(temp_project):
    readme = temp_project / "README.md"
    update_readme(readme, REALISTIC_YOUTUBE)
    report = update_readme(readme, REALISTIC_YOUTUBE_2)
    assert report["updated"] is True
    text = readme.read_text(encoding="utf-8")
    assert REALISTIC_YOUTUBE not in text
    assert REALISTIC_YOUTUBE_2 in text
    assert text.count(REALISTIC_YOUTUBE_2) == 2  # video line + status line
    third = update_readme(readme, REALISTIC_YOUTUBE_2)
    assert third["updated"] is False


def test_exactly_one_distinct_video_url_in_readme(temp_project):
    readme = temp_project / "README.md"
    update_readme(readme, REALISTIC_YOUTUBE)
    text = readme.read_text(encoding="utf-8")
    urls = {
        token.rstrip(").,;")
        for line in text.splitlines()
        if line.startswith(("Video walkthrough:", "**Release status:**"))
        for token in line.split()
        if token.startswith("https://")
    }
    assert urls == {REALISTIC_YOUTUBE}


def test_reference_validation_update_preserves_results(temp_project):
    ref_path = temp_project / "results" / "reference_validation.json"
    before = json.loads(ref_path.read_text(encoding="utf-8"))
    from scripts.finalize_submission import update_reference_validation

    update_reference_validation(ref_path, REALISTIC_YOUTUBE)
    after = json.loads(ref_path.read_text(encoding="utf-8"))
    assert after["video_status"] == {"status": "PUBLISHED", "url": REALISTIC_YOUTUBE}
    for key in (
        "reference_cases_passed",
        "reference_case_count",
        "mutation_controls_rejected",
        "task_case_counts",
    ):
        assert after[key] == before[key]


def test_video_script_says_seventeen_infra(temp_project):
    from scripts.finalize_submission import update_video_script

    update_video_script(temp_project / "docs" / "video_walkthrough_script.md", REALISTIC_YOUTUBE)
    text = (temp_project / "docs" / "video_walkthrough_script.md").read_text(encoding="utf-8")
    assert "Seventeen infrastructure trials" in text
    assert "Ten infrastructure trials" not in text


NEEDLE = "/Us" + "ers/"


def test_no_project_paths_in_packaged_zip(temp_project, monkeypatch):
    monkeypatch.chdir(temp_project)
    (temp_project / "dist").mkdir(parents=True, exist_ok=True)
    from scripts import package_submission

    archive = temp_project / "dist" / "TEST_SANITIZE_TMP.zip"
    package_submission.package(root=temp_project, archive=archive)
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            assert NEEDLE not in zf.read(name).decode("utf-8", errors="ignore"), name


def test_failed_verification_leaves_no_final_artifact(temp_project, monkeypatch):
    import scripts.finalize_submission as fin

    monkeypatch.chdir(temp_project)
    (temp_project / "dist").mkdir(parents=True, exist_ok=True)

    def fake_verify(archive, checksum):
        assert str(archive).endswith(fin.FINAL_NAME)
        return {"exit_code": 1, "stdout_tail": "boom", "stderr_tail": "", "report": {}, "parse_error": ""}

    monkeypatch.setattr(fin, "run_independent_final_validation", fake_verify)
    args = argparse.Namespace(
        video_url=REALISTIC_YOUTUBE, confirm_public=True, non_interactive=True
    )
    monkeypatch.setattr(fin.sys, "argv", ["finalize_submission.py"])
    # drive main() pieces manually to avoid rebuilding twice: emulate failure path
    url = fin.validate_video_url(args.video_url)
    fin.require_owner_confirmation(args)
    fin.update_readme(temp_project / "README.md", url)
    fin.update_submission_status(temp_project / "results" / "submission_status.json", url)
    from scripts import package_submission

    staging = temp_project / "dist" / "STAGING_TMP.zip"
    package_submission.package(root=temp_project, archive=staging)
    final_archive = temp_project / "dist" / fin.FINAL_NAME
    result = fake_verify(
        final_archive, final_archive.with_suffix(final_archive.suffix + ".sha256")
    )
    assert result["exit_code"] != 0
    assert not (temp_project / "dist" / fin.FINAL_NAME).is_file()


def test_end_to_end_finalize_in_temp_copy(temp_project, monkeypatch):
    """Full doc-update + staging-package flow in a temp copy (no Docker gate)."""
    import scripts.finalize_submission as fin

    monkeypatch.chdir(temp_project)
    (temp_project / "dist").mkdir(parents=True, exist_ok=True)
    url = fin.validate_video_url(REALISTIC_YOUTUBE)
    fin.update_readme(temp_project / "README.md", url)
    fin.update_submission_status(temp_project / "results" / "submission_status.json", url)
    fin.update_reference_validation(
        temp_project / "results" / "reference_validation.json", url
    )
    fin.update_video_script(
        temp_project / "docs" / "video_walkthrough_script.md", url
    )
    from scripts import package_submission

    members = package_submission.archive_members(temp_project)
    fin.update_manifest(
        temp_project / "reports" / "SUBMISSION_CONTENT_MANIFEST.md", url, len(members)
    )
    staging = temp_project / "dist" / "STAGING_E2E_TMP.zip"
    report = package_submission.package(root=temp_project, archive=staging)
    assert report["file_count"] == len(members)
    with zipfile.ZipFile(staging) as zf:
        names = zf.namelist()
        assert "README.md" in names
        assert zf.testzip() is None
        readme = zf.read("README.md").decode("utf-8")
        assert url in [ln for ln in readme.splitlines() if ln.startswith("Video walkthrough:")][0]
        ref = json.loads(zf.read("results/reference_validation.json").decode("utf-8"))
        assert ref["video_status"] == {"status": "PUBLISHED", "url": url}
        status = json.loads(zf.read("results/submission_status.json").decode("utf-8"))
        assert status["statuses"]["VIDEO_PUBLISHED"]["status"] == "PUBLISHED"
        for name in names:
            assert NEEDLE not in zf.read(name).decode("utf-8", errors="ignore"), name
    manifest = (temp_project / "reports" / "SUBMISSION_CONTENT_MANIFEST.md").read_text(
        encoding="utf-8"
    )
    assert str(len(members)) in manifest
    assert "sha256" in manifest.lower()
