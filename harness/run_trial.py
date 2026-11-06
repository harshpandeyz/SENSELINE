"""Run one explicitly configured coding agent and grade its output in Docker isolation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from graders.grade import compute_metrics, grade_module
from harness.export_task import export_task
from harness.agent_environment import AgentEnvironmentError, build_agent_environment
from harness.agent_usage import usage_from_event
from harness.secure_execution import DockerCandidate, SANDBOX_IMAGE, SecureExecutionUnavailable, docker_preflight

MASTER_SEED = 20261101


def _expand(value: str, values: dict) -> str:
    return value.format_map(values)


def _quota_exhausted_signal(stdout_text: str) -> bool:
    """Detect provider quota-exhaustion signals in agent stdout.

    Hitting an exhausted free-tier daily quota is not transient: retrying burns
    quota and waiting hours is outside a trial's scope. Callers record the
    signal and stop launching further trials on that configuration.
    """
    haystack = stdout_text or ""
    markers = (
        "free-models-per-day", "FreeUsageLimitError", "free-limit",
        "free_model_daily", "daily requests", "usage limit reached",
        "quotaexceeded", "quota_exceeded", "quota exceeded",
    )
    lowered = haystack.lower()
    if "rate-limit" in haystack.lower() or "rate_limit" in haystack.lower():
        return any(marker in lowered for marker in ("free", "daily", "quota", "limit"))
    return any(marker in lowered for marker in markers)


def _run_version(command, env=None):
    if not command:
        return None
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False, env=env)
        return {"command": _redact_argv(command), "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": _redact_argv(command), "error": str(exc)}


def _redact_argv(command):
    redacted, hide_next = [], False
    sensitive = re.compile(r"(?i)(api[-_]?key|token|secret|password|authorization|credential)")
    for item in command:
        value = str(item)
        if hide_next:
            redacted.append("[REDACTED]")
            hide_next = False
            continue
        if sensitive.search(value) and "=" not in value:
            redacted.append(value)
            hide_next = True
        elif sensitive.search(value) and "=" in value:
            redacted.append(value.split("=", 1)[0] + "=[REDACTED]")
        else:
            redacted.append(value)
    return redacted


def _redact_text(value: str, environment: dict[str, str]) -> str:
    for key, secret in environment.items():
        if secret and re.search(r"(?i)(key|token|secret|password|credential|auth)", key):
            value = value.replace(secret, "[REDACTED]")
    return value


def _redact_mapping(value):
    sensitive = re.compile(r"(?i)(api[-_]?key|token|secret|password|authorization|credential)")
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if sensitive.search(str(key)) else _redact_mapping(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_mapping(item) for item in value]
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_candidate(workspace: Path, snapshot: Path) -> tuple[Path, str | None]:
    """Copy only a bounded regular candidate source; never follow agent-created links."""
    snapshot.mkdir(parents=True, exist_ok=False)
    source, destination = workspace / "solution.py", snapshot / "solution.py"
    try:
        metadata = source.lstat()
    except FileNotFoundError:
        destination.write_text("", encoding="utf-8")
        return destination, "agent did not produce solution.py"
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        destination.write_text("", encoding="utf-8")
        return destination, "solution.py was not a single-link regular file; snapshot was replaced with an empty source"
    if metadata.st_size > 1024 * 1024:
        destination.write_text("", encoding="utf-8")
        return destination, "solution.py exceeded the 1 MiB candidate source limit; snapshot was replaced with an empty source"
    # The agent process has exited, so the checked source cannot be swapped during this copy.
    shutil.copyfile(source, destination, follow_symlinks=False)
    return destination, None


def _append_event(path: Path, event: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")


def _structured_events_from_stdout(stdout: str) -> tuple[list[dict], int]:
    """Return JSON objects the configured agent actually emitted on stdout.

    Codex ``exec --json`` emits JSONL. Some CLI versions may instead emit a
    single JSON document; support both without trying to infer tool activity
    from prose. Raw stdout is retained separately in the trial transcript.
    """
    events: list[dict] = []
    malformed_lines = 0
    nonempty_lines = [line for line in stdout.splitlines() if line.strip()]
    if not nonempty_lines:
        return events, malformed_lines
    for line in nonempty_lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            malformed_lines += 1
            continue
        if isinstance(value, dict):
            events.append(value)
        else:
            malformed_lines += 1
    # Preserve a valid pretty-printed JSON event/document as one actual record.
    if not events and malformed_lines:
        try:
            value = json.loads(stdout)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(value, dict):
                events = [value]
                malformed_lines = 0
    return events, malformed_lines


def _read_agent_events(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    events = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                events.append(item)
            else:
                events.append({"unparsed_agent_event": item, "line": line_number})
        except json.JSONDecodeError:
            events.append({"unparsed_agent_event_line": line, "line": line_number})
    return events


def _terminate_agent_process(process: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, 15)
        else:
            process.terminate()
        process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        try:
            if os.name == "posix":
                os.killpg(process.pid, 9)
            else:
                process.kill()
        except OSError:
            pass


def _run_agent_with_limits(command, cwd, env, timeout_seconds, token_budget=None,
                           max_cost_usd=None, input_rate=None, output_rate=None):
    """Stream actual JSONL usage, enforce wall/token/estimated-cost caps, and retain raw IO."""
    process = subprocess.Popen(
        command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
        start_new_session=(os.name == "posix"),
    )
    stdout_lines, stderr_lines, usage_records = [], [], []
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    estimated_cost = Decimal(0)
    cost_estimate_complete = True
    budget_stop_reason = None
    lock = threading.Lock()

    def read_stdout():
        nonlocal estimated_cost, cost_estimate_complete, budget_stop_reason
        for line in iter(process.stdout.readline, ""):
            stdout_lines.append(line)
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            usage = usage_from_event(event)
            if usage is None:
                continue
            with lock:
                usage_records.append(usage)
                for key in totals:
                    totals[key] += usage.get(key) or 0
                if usage.get("input_tokens") is None or usage.get("output_tokens") is None or input_rate is None or output_rate is None:
                    cost_estimate_complete = False
                else:
                    estimated_cost += (
                        Decimal(usage["input_tokens"]) * Decimal(str(input_rate))
                        + Decimal(usage["output_tokens"]) * Decimal(str(output_rate))
                    ) / Decimal(1_000_000)
                exceeded = token_budget is not None and totals["total_tokens"] > token_budget
                cost_exceeded = max_cost_usd is not None and cost_estimate_complete and estimated_cost > Decimal(str(max_cost_usd))
                if exceeded:
                    budget_stop_reason = "token_budget_exceeded"
                elif cost_exceeded:
                    budget_stop_reason = "estimated_trial_cost_cap_exceeded"
            if budget_stop_reason and process.poll() is None:
                _terminate_agent_process(process)
        process.stdout.close()

    def read_stderr():
        for line in iter(process.stderr.readline, ""):
            stderr_lines.append(line)
        process.stderr.close()

    stdout_thread = threading.Thread(target=read_stdout, daemon=True)
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    started = time.monotonic()
    stdout_thread.start()
    stderr_thread.start()
    timed_out = False
    while process.poll() is None:
        if time.monotonic() - started >= timeout_seconds:
            timed_out = True
            _terminate_agent_process(process)
            break
        time.sleep(0.025)
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        _terminate_agent_process(process)
    stdout_thread.join(timeout=3)
    stderr_thread.join(timeout=3)
    elapsed = time.monotonic() - started
    usage = {
        **totals,
        "events": usage_records,
        "reported": bool(usage_records),
        "estimated_cost_complete": cost_estimate_complete and bool(usage_records),
        "estimated_cost_usd": str(estimated_cost) if cost_estimate_complete and usage_records else None,
        "confirmed_cost_usd": None,
        "budget_stop_reason": budget_stop_reason,
    }
    return {
        "returncode": process.returncode,
        "stdout": "".join(stdout_lines),
        "stderr": "".join(stderr_lines),
        "timed_out": timed_out,
        "runtime_seconds": elapsed,
        "usage": usage,
    }


def run_trial(task, profile_path, model_id, trial, timeout, output_dir, cost_usd=None,
              candidate_timeout=5.0, trial_configuration=None):
    # Fail closed before invoking an agent; no model/API call is made without the required sandbox.
    isolation = docker_preflight(SANDBOX_IMAGE)
    profile_path = Path(profile_path).resolve()
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    agent = profile["name"]
    output_dir = Path(output_dir).resolve()
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')}_{task}_{agent}_trial{trial}"
    runs = output_dir / "runs" / run_id
    work_parent = Path(tempfile.mkdtemp(prefix=f"senseline-{task.lower()}-{trial}-"))
    work = work_parent / "workspace"
    runs.mkdir(parents=True, exist_ok=False)
    event_path = runs / "events.jsonl"
    started = datetime.now(timezone.utc).isoformat()
    task_index = int(task[1:])
    trial_seed = MASTER_SEED + task_index * 1009 + trial * 100003
    _append_event(event_path, {"event": "trial_started", "run_id": run_id, "task": task, "trial": trial, "trial_seed": trial_seed, "started_at_utc": started, "isolation": isolation})

    export_task(task, work)
    task_instruction = (work / "task.md").read_text(encoding="utf-8")
    prompt = (
        task_instruction
        + "\n\nImplementation instruction: edit only solution.py in the current task workspace. "
        + "Implement solve(payload: dict) -> dict. Do not add dependencies. The evaluator runs each test input "
        + "in a network-disabled Docker container using the pinned Python 3.11.18 runtime. "
        + f"Trial reproducibility seed: {trial_seed}.\n"
    )
    agent_events_path = runs / "agent-events.jsonl"
    agent_home = work / ".senseline-agent-home"
    agent_home.mkdir(mode=0o700)
    opencode_config_dir = agent_home / "opencode"
    opencode_config_dir.mkdir(mode=0o700)
    opencode_policy_path = agent_home / "opencode_task_permissions.json"
    if agent == "opencode":
        shutil.copyfile(ROOT / "configs" / "opencode_task_permissions.json", opencode_policy_path)
    values = {
        "workspace": str(work), "prompt": prompt, "model": model_id,
        "events": str(agent_events_path), "agent_home": str(agent_home),
        "opencode_config_dir": str(opencode_config_dir),
        "opencode_policy_path": str(opencode_policy_path),
    }
    command = [_expand(str(part), values) for part in profile["command"]]
    t0 = time.monotonic()
    timed_out = False
    usage_report = {
        "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "events": [],
        "reported": False, "estimated_cost_complete": False,
        "estimated_cost_usd": None, "confirmed_cost_usd": cost_usd,
        "budget_stop_reason": "not_monitored",
    }
    setup_error = None
    agent_env, environment_audit = {}, {}
    effective_profile = dict(profile)
    if trial_configuration and "credential_env" in trial_configuration:
        effective_profile["credential_env"] = trial_configuration["credential_env"]
    budget_data = (trial_configuration or {}).get("budget", {})
    credential_names = effective_profile.get("credential_env", [])
    max_trial_cost = budget_data.get("max_cost_per_trial_usd")
    token_budget = budget_data.get("max_total_tokens_per_trial")
    input_rate = budget_data.get("input_usd_per_million_tokens")
    output_rate = budget_data.get("output_usd_per_million_tokens")
    zero_cost = isinstance(trial_configuration, dict) and trial_configuration.get("cost_tier") == "zero_cost"
    if agent in ("codex-cli", "opencode") and not credential_names and not zero_cost:
        setup_error = "model agent requires an explicitly named dedicated provider credential; host auth files are not used"
    elif zero_cost and (
        max_trial_cost != 0 or input_rate != 0 or output_rate != 0
        or not isinstance((trial_configuration or {}).get("registered_cost_cap_usd"), (int, float))
        or not isinstance((trial_configuration or {}).get("provider_hard_spend_limit_usd"), (int, float))
    ):
        setup_error = "zero-cost trial requires exact-zero monetary caps/rates and registered zero spend controls"
    elif zero_cost and (
        not isinstance(token_budget, int) or isinstance(token_budget, bool) or token_budget <= 0
    ):
        setup_error = "zero-cost trial still requires a positive max_total_tokens_per_trial"
    elif credential_names and not zero_cost and (
        not isinstance(max_trial_cost, (int, float)) or isinstance(max_trial_cost, bool) or max_trial_cost <= 0
        or not isinstance(token_budget, int) or isinstance(token_budget, bool) or token_budget <= 0
        or not isinstance(input_rate, (int, float)) or isinstance(input_rate, bool) or input_rate <= 0
        or not isinstance(output_rate, (int, float)) or isinstance(output_rate, bool) or output_rate <= 0
        or not isinstance((trial_configuration or {}).get("registered_cost_cap_usd"), (int, float))
        or not isinstance((trial_configuration or {}).get("provider_hard_spend_limit_usd"), (int, float))
    ):
        setup_error = "model trial requires experiment/provider caps, per-trial USD cap, token budget, and input/output token rates"
    if setup_error is None:
        try:
            agent_env, environment_audit = build_agent_environment(effective_profile, values, work)
        except AgentEnvironmentError as exc:
            setup_error = str(exc)
    _append_event(event_path, {
        "event": "agent_command_started", "command": _redact_argv(command),
        "model_id": model_id, "profile_name": agent,
        "environment_security_audit": environment_audit,
        "setup_blocked": setup_error is not None,
        "setup_block_reason": setup_error,
    })
    def _infra_retry_eligible(stdout_text: str, exit_code_value, was_timed_out: bool,
                              seconds: float, usage: dict) -> bool:
        """Detect fast provider-resolution failures worth one bounded retry.

        Only zero-cost trials may retry: no charge is possible by construction
        (local models or documented $0 models), so a retry cannot conceal spend.
        Retries never apply after a token/cost budget stop, a timeout, a setup
        block, when usage was reported, or on rate-limit/quota signals (retrying
        an exhausted quota is pointless and burns quota). Every attempt is
        recorded in the event log; the final attempt's output is what gets graded.
        """
        if not zero_cost or setup_error or was_timed_out:
            return False
        if usage.get("reported") or usage.get("budget_stop_reason"):
            return False
        if exit_code_value == 0 or seconds >= 120:
            return False
        haystack = stdout_text or ""
        if _quota_exhausted_signal(haystack):
            return False
        return ('"type":"error"' in haystack and (
            "no-route" in haystack or "Model unavailable" in haystack
            or "timeout" in haystack.lower()))

    def _launch_agent_once():
        if setup_error:
            return "", f"agent setup blocked: {setup_error}", None, False, dict(usage_report)
        # This allowlisted environment contains only a dedicated provider key (or
        # no secrets at all for zero-cost local models).
        # Candidate Docker execution receives no part of this environment.
        if credential_names or zero_cost:
            finished = _run_agent_with_limits(
                command, work, agent_env, timeout, token_budget,
                max_trial_cost, input_rate, output_rate,
            )
            return (
                _redact_text(finished["stdout"], agent_env),
                _redact_text(finished["stderr"], agent_env),
                finished["returncode"], finished["timed_out"], finished["usage"],
            )
        finished = subprocess.run(command, cwd=work, capture_output=True, text=True, timeout=timeout, check=False, env=agent_env)
        return (
            _redact_text(finished.stdout, agent_env),
            _redact_text(finished.stderr, agent_env),
            finished.returncode, False, dict(usage_report),
        )

    try:
        stdout, stderr, exit_code, timed_out, usage_report = _launch_agent_once()
        attempt = 1
        attempt_elapsed = time.monotonic() - t0
        while _infra_retry_eligible(stdout, exit_code, timed_out, attempt_elapsed, usage_report) and attempt <= 2:
            wait_seconds = 30 if attempt == 1 else 90
            _append_event(event_path, {
                "event": "agent_command_infra_retry",
                "attempt": attempt + 1,
                "previous_exit_code": exit_code,
                "previous_runtime_seconds": attempt_elapsed,
                "wait_seconds": wait_seconds,
                "reason": "fast provider-resolution failure with no usage metadata on a zero-cost trial; retrying with the same trial seed",
            })
            time.sleep(wait_seconds)
            stdout, stderr, exit_code, timed_out, usage_report = _launch_agent_once()
            attempt += 1
            attempt_elapsed = time.monotonic() - t0
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        raw_stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        raw_stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        stdout, stderr, exit_code = _redact_text(raw_stdout, agent_env), _redact_text(raw_stderr, agent_env), None
    except OSError as exc:
        stdout, stderr, exit_code = "", f"could not start configured agent: {exc}", None
    elapsed = time.monotonic() - t0
    if profile.get("structured_stdout_jsonl"):
        emitted, malformed_event_lines = _structured_events_from_stdout(stdout)
        for item in emitted:
            _append_event(event_path, {
                "event": "agent_reported_structured_event",
                "source": "agent_stdout_jsonl",
                "data": _redact_mapping(item),
            })
        if malformed_event_lines:
            _append_event(event_path, {
                "event": "agent_structured_stdout_unparsed_lines",
                "count": malformed_event_lines,
                "note": "Raw stdout remains in the transcript; no event was inferred from these lines.",
            })
    _append_event(event_path, {
        "event": "agent_command_completed", "exit_code": exit_code,
        "timed_out": timed_out, "runtime_seconds": elapsed,
        "stdout": stdout, "stderr": stderr, "usage": usage_report,
    })

    safe_version_env = {key: value for key, value in agent_env.items() if not re.search(r"(?i)(key|token|secret|password|credential|auth)", key)}
    agent_version = _run_version(profile.get("version_command"), env=safe_version_env) if not setup_error else None
    snapshot = runs / "workspace"
    source, source_snapshot_issue = _snapshot_candidate(work, snapshot)
    if source_snapshot_issue:
        _append_event(event_path, {"event": "candidate_source_snapshot_rejected", "reason": source_snapshot_issue})
    shutil.rmtree(work_parent, ignore_errors=True)
    source_hash = _sha256(source)
    runtime_events = []
    docker_candidate = DockerCandidate(source, candidate_timeout, SANDBOX_IMAGE, event_sink=lambda event: _append_event(event_path, event), preflight=isolation)

    def record_case(row):
        _append_event(event_path, {
            "event": "grader_case_completed", "case_id": row["id"],
            "passed": row["passed"], "failure_dimensions": row["failure_dimensions"],
            "candidate_output": row["actual"], "execution_error": row["error"],
        })

    runtime_events = _read_agent_events(agent_events_path)
    if runtime_events:
        for item in runtime_events:
            _append_event(event_path, {"event": "agent_reported_structured_event", "source": "configured_agent_event_file", "data": _redact_mapping(item)})

    try:
        scored = grade_module(task, docker_candidate, str(source), on_case=record_case)
    except SecureExecutionUnavailable as exc:
        # Docker can disappear after preflight. Preserve all evidence and stop without
        # attempting a host-Python fallback or silently losing an already-started trial.
        failure = {
            "status": "SECURE_EVALUATION_UNAVAILABLE", "reason": str(exc),
            "run_id": run_id, "task": task, "trial": trial, "trial_seed": trial_seed,
            "agent": agent, "agent_version": agent_version, "model_id": model_id,
            "profile": str(profile_path), "profile_configuration": _redact_mapping(profile),
            "experiment_configuration": _redact_mapping(trial_configuration or {}),
            "started_at_utc": started, "runtime_seconds": elapsed,
            "timeout_seconds": timeout, "candidate_timeout_seconds": candidate_timeout,
            "cost_usd": cost_usd, "cost_usd_estimated": usage_report.get("estimated_cost_usd"),
            "cost_usd_confirmed": cost_usd, "usage": usage_report,
            "exit_code": exit_code, "timed_out": timed_out,
            "candidate_source_path": str(source), "candidate_source_sha256": source_hash,
            "candidate_source_snapshot_issue": source_snapshot_issue,
            "exact_task_instruction": task_instruction, "prompt": prompt,
            "agent_command": _redact_argv(command), "agent_stdout": stdout, "agent_stderr": stderr,
            "sandbox": isolation, "event_log_path": str(event_path),
            "tool_event_capture": "agent-reported structured events only; no private reasoning is captured",
        }
        _append_event(event_path, {"event": "secure_execution_unavailable", "reason": str(exc)})
        transcript_path = output_dir / "transcripts" / f"{run_id}.jsonl"
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        (runs / "transcript.json").write_text(json.dumps(failure, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        transcript_path.write_text(event_path.read_text(encoding="utf-8") + json.dumps({"event": "complete_transcript", "data": failure}, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
        (runs / "trial_index.json").write_text(json.dumps(failure, indent=2, default=str) + "\n", encoding="utf-8")
        raise

    score_path = runs / "score.json"
    transcript_path = output_dir / "transcripts" / f"{run_id}.jsonl"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    metrics = compute_metrics([scored])
    run_result = {
        "run_id": run_id, "task": task, "trial": trial, "trial_seed": trial_seed,
        "agent": agent, "agent_version": agent_version, "model_id": model_id,
        "quota_exhausted": _quota_exhausted_signal(stdout),
        "profile": str(profile_path), "profile_configuration": _redact_mapping(profile),
        "experiment_configuration": _redact_mapping(trial_configuration or {}),
        "started_at_utc": started, "runtime_seconds": elapsed, "timeout_seconds": timeout,
        "candidate_timeout_seconds": candidate_timeout, "timed_out": timed_out,
        "exit_code": exit_code, "cost_usd": cost_usd,
        "cost_usd_estimated": usage_report.get("estimated_cost_usd"),
        "cost_usd_confirmed": cost_usd, "usage": usage_report,
        "candidate_source_path": str(source), "candidate_source_sha256": source_hash,
        "candidate_source_snapshot_issue": source_snapshot_issue,
        "task_accuracy": scored["accuracy"], "score_path": str(score_path),
        "workspace_path": str(snapshot), "sandbox": isolation,
        "structured_agent_event_count": len(runtime_events),
    }
    transcript = {
        **run_result, "exact_task_instruction": task_instruction, "prompt": prompt,
        "agent_command": _redact_argv(command), "agent_stdout": stdout, "agent_stderr": stderr,
        "agent_version_record": agent_version, "metrics": metrics, "grader": scored,
        "event_log_path": str(event_path),
        "tool_event_capture": "agent-reported structured events only; no private reasoning is captured",
    }
    _append_event(event_path, {"event": "grading_completed", "task_accuracy": scored["accuracy"], "metrics": metrics, "candidate_source_sha256": source_hash})
    transcript_text = json.dumps({**transcript, "transcript_path": str(transcript_path)}, indent=2, ensure_ascii=False) + "\n"
    (runs / "transcript.json").write_text(transcript_text, encoding="utf-8")
    transcript_path.write_text(event_path.read_text(encoding="utf-8") + json.dumps({"event": "complete_transcript", "data": transcript}, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    score_path.write_text(json.dumps({**run_result, "metrics": metrics, "grader": scored}, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    flat = {**run_result, "cases_passed": scored["passed"], "case_count": scored["case_count"]}
    (runs / "trial_index.json").write_text(json.dumps(flat, indent=2, default=str) + "\n", encoding="utf-8")
    return run_result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, choices=[f"S{i:02}" for i in range(1, 9)])
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--model-id", required=True, help="Exact model identifier supplied to the agent adapter")
    parser.add_argument("--trial", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=900, help="Agent wall-clock timeout in seconds")
    parser.add_argument("--candidate-timeout", type=float, default=5.0, help="Per-input isolated candidate timeout")
    parser.add_argument("--cost-usd", type=float, default=None, help="Record externally measured cost, if known")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    try:
        result = run_trial(args.task, args.profile, args.model_id, args.trial, args.timeout, args.output_dir, args.cost_usd, args.candidate_timeout)
    except SecureExecutionUnavailable as exc:
        print(json.dumps({"status": "SECURE_EVALUATION_UNAVAILABLE", "reason": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
