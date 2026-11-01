"""Minimal environment and private HOME construction for coding-agent trials."""
from __future__ import annotations

import os
import json
import re
from pathlib import Path

BASE_ENV_ALLOWLIST = ("PATH", "LANG", "LC_ALL", "TERM", "NO_COLOR")
PROVIDER_CREDENTIAL_ENV_ALLOWLIST = frozenset({
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_GENERATIVE_AI_API_KEY",
    "NVIDIA_API_KEY",
    "OPENROUTER_API_KEY",
    "META_API_KEY",
})
PROFILE_ENV_ALLOWLISTS = {
    "codex-cli": frozenset(),
    "opencode": frozenset({
        "OPENCODE_CONFIG", "OPENCODE_CONFIG_DIR", "OPENCODE_DISABLE_PROJECT_CONFIG",
        "OPENCODE_DISABLE_EXTERNAL_SKILLS", "OPENCODE_DISABLE_CLAUDE_CODE",
        "OPENCODE_DISABLE_AUTOUPDATE",
    }),
    "generic-command": frozenset(),
}
_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


class AgentEnvironmentError(RuntimeError):
    """Raised when an agent profile requests unsupported or missing environment access."""


def build_agent_environment(profile: dict, values: dict, workspace: Path, source_env=None) -> tuple[dict[str, str], dict]:
    """Build environment from an allowlist; never copy the launcher's full environment.

    Host state is used only to read explicitly allowlisted nonsecret runtime
    variables and specifically named provider API keys. HOME, XDG paths, Codex
    state, OpenCode config/data and npm/git config are replaced with private,
    task-local paths. Host auth files are not copied or mounted.
    """
    source_env = os.environ if source_env is None else source_env
    workspace = Path(workspace).resolve()
    private_home = workspace / ".senseline-agent-home"
    scratch = workspace / ".senseline-agent-tmp"
    private_home.mkdir(mode=0o700, exist_ok=True)
    scratch.mkdir(mode=0o700, exist_ok=True)
    codex_home = private_home / ".codex"
    opencode_data = private_home / "opencode"
    xdg_config = private_home / "xdg-config"
    xdg_cache = private_home / "xdg-cache"
    xdg_data = private_home / "xdg-data"
    npm_cache = private_home / "npm-cache"
    for path in (codex_home, opencode_data, xdg_config, xdg_cache, xdg_data, npm_cache):
        path.mkdir(mode=0o700, exist_ok=True)

    env = {name: source_env[name] for name in BASE_ENV_ALLOWLIST if source_env.get(name)}
    env.update({
        "HOME": str(private_home),
        "TMPDIR": str(scratch),
        "TMP": str(scratch),
        "TEMP": str(scratch),
        "CODEX_HOME": str(codex_home),
        "XDG_CONFIG_HOME": str(xdg_config),
        "XDG_CACHE_HOME": str(xdg_cache),
        "XDG_DATA_HOME": str(xdg_data),
        "NPM_CONFIG_CACHE": str(npm_cache),
        "NPM_CONFIG_USERCONFIG": str(private_home / ".npmrc"),
        "NPM_CONFIG_GLOBALCONFIG": str(private_home / "npmrc-global"),
        "NPM_CONFIG_AUDIT": "false",
        "NPM_CONFIG_FUND": "false",
        "GIT_CONFIG_GLOBAL": str(private_home / ".gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
    })
    for name in (".npmrc", "npmrc-global", ".gitconfig"):
        (private_home / name).touch(mode=0o600, exist_ok=True)

    # Codex loads only this trial-local configuration. Its own shell commands
    # inherit no agent-process variables, including provider credentials.
    if profile.get("name") == "codex-cli":
        config = (
            'default_permissions = "senseline-task"\n'
            'approval_policy = "on-request"\n'
            '[shell_environment_policy]\n'
            'inherit = "none"\n'
            'ignore_default_excludes = false\n'
            '[shell_environment_policy.set]\n'
            f'PATH = {json.dumps(env.get("PATH", os.defpath))}\n'
            f'HOME = {json.dumps(str(private_home))}\n'
            f'TMPDIR = {json.dumps(str(scratch))}\n'
            f'TMP = {json.dumps(str(scratch))}\n'
            f'TEMP = {json.dumps(str(scratch))}\n'
            '[permissions.senseline-task.filesystem]\n'
            '":minimal" = "read"\n'
            '[permissions.senseline-task.filesystem.":workspace_roots"]\n'
            '"." = "write"\n'
            '[permissions.senseline-task.network]\n'
            'enabled = false\n'
        )
        (codex_home / "config.toml").write_text(config, encoding="utf-8")
        (codex_home / "config.toml").chmod(0o600)

    configured_allowlist = profile.get("environment_allowlist", [])
    if not isinstance(configured_allowlist, list) or any(not isinstance(name, str) for name in configured_allowlist):
        raise AgentEnvironmentError("profile environment_allowlist must be a list of names")
    known_profile_names = PROFILE_ENV_ALLOWLISTS.get(profile.get("name"), frozenset())
    if not set(configured_allowlist).issubset(known_profile_names):
        raise AgentEnvironmentError("profile requests a runtime variable outside the implementation allowlist")
    configured_environment = profile.get("environment", {})
    if not isinstance(configured_environment, dict) or not set(configured_environment).issubset(set(configured_allowlist)):
        raise AgentEnvironmentError("profile environment values must be limited to environment_allowlist")
    for name, template in configured_environment.items():
        if not isinstance(template, str):
            raise AgentEnvironmentError("profile environment values must be strings")
        env[name] = template.format_map(values)

    credential_names = profile.get("credential_env", [])
    if not isinstance(credential_names, list):
        raise AgentEnvironmentError("credential_env must be a list of provider credential variable names")
    for name in credential_names:
        if not isinstance(name, str) or not _ENV_NAME.fullmatch(name) or name not in PROVIDER_CREDENTIAL_ENV_ALLOWLIST:
            raise AgentEnvironmentError(f"unsupported provider credential environment name: {name!r}")
        secret = source_env.get(name)
        if not secret:
            raise AgentEnvironmentError(f"required dedicated provider credential {name} is not configured")
        env[name] = secret

    audit = {
        "inherited_environment_names": sorted(name for name in BASE_ENV_ALLOWLIST if name in env),
        "profile_environment_names": sorted(configured_environment),
        "provider_credential_names": sorted(credential_names),
        "home_is_task_local": private_home.is_relative_to(workspace),
        "codex_home_is_task_local_and_fresh": codex_home.is_relative_to(workspace) and not (codex_home / "auth.json").exists(),
        "xdg_and_cli_config_are_task_local": all(path.is_relative_to(workspace) for path in (xdg_config, xdg_cache, xdg_data, opencode_data)),
        "host_home_inherited": False,
    }
    return env, audit

