"""Verify task-local agent environments and the installed Codex OS sandbox without model calls."""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from harness.agent_environment import build_agent_environment


def _run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=15, check=False)


def verify() -> dict:
    codex = shutil.which("codex")
    if not codex:
        raise RuntimeError("installed Codex CLI is required to verify agent sandbox behavior")
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="senseline-agent-security-") as temp:
        root = Path(temp)
        workspace = root / "task-workspace"
        workspace.mkdir()
        host_home = root / "host-home"
        host_credential = host_home / ".codex" / "auth.json"
        host_credential.parent.mkdir(parents=True)
        host_credential.write_text("SENSELINE_HOST_CREDENTIAL_SENTINEL", encoding="utf-8")
        hidden_grader = root / "hidden-grader" / "S08.json"
        hidden_grader.parent.mkdir()
        hidden_grader.write_text("SENSELINE_HIDDEN_GRADER_SENTINEL", encoding="utf-8")
        evaluator = root / "evaluator.py"
        evaluator.write_text("SENSELINE_EVALUATOR_SENTINEL", encoding="utf-8")
        env, audit = build_agent_environment(
            {"name": "codex-cli", "credential_env": []}, {}, workspace,
            {
                "PATH": os.environ.get("PATH", os.defpath),
                "HOME": str(host_home),
                "GITHUB_TOKEN": "injected-github-secret",
                "AWS_SECRET_ACCESS_KEY": "injected-cloud-secret",
                "DATABASE_URL": "injected-database-secret",
                "SENSELINE_TEST_SECRET": "injected-test-secret",
            },
        )
        checks["credential_variables_excluded_from_agent_environment"] = not any(
            name in env for name in ("GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY", "DATABASE_URL", "SENSELINE_TEST_SECRET")
        )
        checks["host_home_and_auth_not_inherited"] = env["HOME"] != str(host_home) and not Path(env["CODEX_HOME"], "auth.json").exists()
        version = _run([codex, "--version"], workspace, env)
        if version.returncode:
            raise RuntimeError(f"Codex version check failed: {version.stderr[-1000:]}")

        def sandbox(command: list[str]) -> subprocess.CompletedProcess:
            return _run([
                codex, "sandbox", "--permission-profile", "senseline-task",
                "--cd", str(workspace), "--log-denials", *command,
            ], workspace, env)

        allowed_write = workspace / "candidate-edit.txt"
        inside = sandbox(["/usr/bin/touch", str(allowed_write)])
        checks["task_workspace_write_allowed"] = inside.returncode == 0 and allowed_write.is_file()
        outside_checks = []
        for protected in (host_credential, hidden_grader, evaluator):
            response = sandbox(["/bin/cat", str(protected)])
            outside_checks.append(response.returncode != 0 and "SENSELINE_" not in response.stdout + response.stderr)
        checks["host_credentials_hidden_graders_and_evaluator_inaccessible"] = all(outside_checks)

        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        def accept_once():
            try:
                accepted, _ = listener.accept()
                accepted.close()
            except OSError:
                pass

        thread = threading.Thread(target=accept_once, daemon=True)
        thread.start()
        python = "/usr/bin/python3"
        network = sandbox([
            python, "-c",
            f"import socket; s=socket.create_connection(('127.0.0.1',{port}),timeout=2); print('CONNECTED'); s.close()",
        ])
        listener.close()
        checks["agent_shell_network_disabled"] = network.returncode != 0 or "CONNECTED" not in network.stdout
        checks["shell_environment_does_not_inherit_provider_credentials"] = 'inherit = "none"' in Path(env["CODEX_HOME"], "config.toml").read_text()
        checks["candidate_environment_is_not_used_here"] = True
        result = {
            "status": "PASS" if all(checks.values()) else "FAIL",
            "codex_version": version.stdout.strip(),
            "codex_home_is_temporary": audit["codex_home_is_task_local_and_fresh"],
            "checks": checks,
            "model_inference_performed": False,
            "provider_credentials_injected": False,
            "limitation": "This exercises Codex's actual macOS sandbox command without model inference. It does not test a provider API key; a dedicated scoped key remains exposed to the agent CLI process when inference is later enabled.",
        }
        if not all(checks.values()):
            raise RuntimeError(json.dumps(result, indent=2))
        return result


if __name__ == "__main__":
    report = verify()
    output = ROOT / "results" / "agent_security_validation.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))

