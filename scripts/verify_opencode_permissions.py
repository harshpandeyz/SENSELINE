"""Resolve the pinned OpenCode v2 permissions in a disposable task project."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from harness.agent_environment import build_agent_environment

CONFIG = ROOT / "configs" / "opencode_task_permissions.json"
COMMAND = [
    "npm", "exec", "--yes", "--package=@opencode/cli@2.2.5", "--",
    "opencode", "--standalone", "debug", "config",
]


def verify() -> dict:
    with tempfile.TemporaryDirectory(prefix="senseline-opencode-verification-") as temp:
        base = Path(temp)
        workspace = base / "task-workspace"
        workspace.mkdir()
        (workspace / "solution.py").write_text("def solve(payload):\n    return {}\n", encoding="utf-8")
        (base / "hidden-parent-sentinel.txt").write_text("must remain outside the task project", encoding="utf-8")
        agent_home = workspace / ".senseline-agent-home"
        agent_home.mkdir(mode=0o700)
        config_dir = agent_home / "opencode"
        config_dir.mkdir(mode=0o700)
        policy_copy = agent_home / "opencode_task_permissions.json"
        shutil.copyfile(CONFIG, policy_copy)
        profile = {
            "name": "opencode",
            "environment_allowlist": ["OPENCODE_CONFIG", "OPENCODE_CONFIG_DIR", "OPENCODE_DISABLE_PROJECT_CONFIG", "OPENCODE_DISABLE_EXTERNAL_SKILLS", "OPENCODE_DISABLE_CLAUDE_CODE", "OPENCODE_DISABLE_AUTOUPDATE"],
            "credential_env": [],
            "environment": {
                "OPENCODE_CONFIG": str(policy_copy),
                "OPENCODE_CONFIG_DIR": str(config_dir),
                "OPENCODE_DISABLE_PROJECT_CONFIG": "true",
                "OPENCODE_DISABLE_EXTERNAL_SKILLS": "true",
                "OPENCODE_DISABLE_CLAUDE_CODE": "true",
                "OPENCODE_DISABLE_AUTOUPDATE": "true",
            },
        }
        env, env_audit = build_agent_environment(
            profile, {}, workspace,
            {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(Path.home()), "GITHUB_TOKEN": "must-not-inherit"},
        )
        version = subprocess.run(
            ["npm", "exec", "--yes", "--package=@opencode/cli@2.2.5", "--", "opencode", "--version"],
            cwd=workspace, env=env, capture_output=True, text=True, timeout=60, check=True,
        ).stdout.strip()
        if version != "opencode v2.2.5":
            raise RuntimeError(f"expected OpenCode v2.2.5, got {version!r}")
        resolved = subprocess.run(
            COMMAND, cwd=workspace, env=env, capture_output=True, text=True, timeout=60, check=True,
        )
        sources = json.loads(resolved.stdout)
        loaded = next((item for item in sources if item.get("path") == str(policy_copy)), None)
        if not loaded:
            raise RuntimeError("OpenCode CLI did not load the designated task-permissions file")
        rules = loaded.get("info", {}).get("permissions")
        if not isinstance(rules, list):
            raise RuntimeError("OpenCode CLI did not parse a v2 permissions array")
        if not any(rule == {"action": "external_directory", "resource": "*", "effect": "deny"} for rule in rules):
            raise RuntimeError("resolved configuration does not deny external directories")
        if not any(rule == {"action": "shell", "resource": "*", "effect": "deny"} for rule in rules):
            raise RuntimeError("resolved configuration does not deny shell execution")
        if not any(rule.get("action") == "edit" and rule.get("resource") in ("solution.py", "**/solution.py") and rule.get("effect") == "allow" for rule in rules):
            raise RuntimeError("resolved configuration does not allow solution.py editing")
        return {
            "status": "CLI_CONFIG_RESOLVED",
            "opencode_version": version,
            "task_workspace_created_fresh": True,
            "parent_sentinel_created_outside_workspace": True,
            "permissions_config_sha256": hashlib.sha256(policy_copy.read_bytes()).hexdigest(),
            "permissions_loaded_by_actual_cli": True,
            "external_directory_denied": True,
            "shell_denied": True,
            "solution_py_edit_allowed": True,
            "model_inference_performed": False,
            "dynamic_tool_denial_exercised": False,
            "host_credential_environment_inherited": "GITHUB_TOKEN" in env,
            "private_home_is_task_local": env_audit["home_is_task_local"],
            "limitation": "This verifies v2 configuration loading in a disposable project with a task-local HOME and no host credentials; it does not claim an agent tool call was dynamically denied. Shell is disabled, and candidate execution is separately validated in Docker.",
        }


if __name__ == "__main__":
    result = verify()
    destination = ROOT / "results" / "opencode_permission_verification.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
