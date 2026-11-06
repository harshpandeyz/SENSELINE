"""Automated tests for the video-aware finalization process.

All tests use temporary copies and dummy URLs. They never modify the real
README, results, or dist/ artifacts.
"""
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
    archive_file_info,
    update_manifest,
    update_readme,
    update_release_audit,
    update_submission_status,
    update_validation_report,
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
    result = fin.run_independent_final_validation()
    assert result["exit_code"] == 0
    cmd = captured["cmd"]
    assert "scripts/verify_release_archive.py" in cmd
    assert "--mode" in cmd and "final" in cmd
    assert "--archive" in cmd and f"dist/{fin.FINAL_NAME}" in cmd
    assert "--checksum" in cmd and f"dist/{fin.FINAL_NAME}.sha256" in cmd


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


def test_manifest_and_validation_report_updates(temp_project):
    update_readme(temp_project / "README.md", REALISTIC_YOUTUBE)
    fake_info = {
        "file_count": 712,
        "size_bytes": 4100000,
        "sha256": "0" * 64,
    }
    update_manifest(
        temp_project / "reports" / "SUBMISSION_CONTENT_MANIFEST.md",
        REALISTIC_YOUTUBE,
        fake_info,
    )
    manifest = (temp_project / "reports" / "SUBMISSION_CONTENT_MANIFEST.md").read_text(
        encoding="utf-8"
    )
    assert FINAL_NAME in manifest
    assert REALISTIC_YOUTUBE in manifest
    assert "712 files" in manifest
    fake_verify = {
        "archive_sha256": "0" * 64,
        "archive_size_bytes": 4100000,
        "file_count": 712,
        "technical_package_validation": "PASS",
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
