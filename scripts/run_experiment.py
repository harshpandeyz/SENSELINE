"""Plan or explicitly execute the three-configuration SENSELINE experiment."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.run_trial import run_trial
from harness.secure_execution import SANDBOX_IMAGE, docker_preflight


def _is_zero_cost(config: dict) -> bool:
    """A configuration is zero-cost only when explicitly declared and fully zero-rated.

    Zero-cost tiers cover local models (no credential) and documented $0/free-tier
    provider models. They still require token budgets and reported usage metadata;
    only the monetary caps and credential requirements are relaxed to exact zero.
    """
    if config.get("cost_tier") != "zero_cost":
        return False
    budget = config.get("budget", {})
    for key in ("input_usd_per_million_tokens", "output_usd_per_million_tokens"):
        value = budget.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value != 0:
            return False
    per_run = budget.get("max_cost_per_trial_usd")
    return isinstance(per_run, (int, float)) and not isinstance(per_run, bool) and per_run == 0


def load_matrix(path: Path, require_models: bool = True) -> dict:
    matrix = json.loads(path.read_text(encoding="utf-8"))
    configs = matrix.get("configurations", [])
    if len(configs) != 3:
        raise ValueError("experiment matrix must define exactly three configurations")
    names = set()
    for item in configs:
        if not item.get("name") or item["name"] in names:
            raise ValueError("each configuration needs a unique nonempty name")
        names.add(item["name"])
        if require_models and (not item.get("model_id") or not isinstance(item["model_id"], str)):
            raise ValueError(f"{item['name']} needs an exact model_id before execution")
        if require_models and (not item.get("agent_version_expected") or not isinstance(item["agent_version_expected"], str)):
            raise ValueError(f"{item['name']} needs an exact agent_version_expected from its configured version command")
        if _is_zero_cost(item):
            if not isinstance(item.get("budget", {}).get("max_total_tokens_per_trial"), int) or isinstance(item["budget"]["max_total_tokens_per_trial"], bool) or item["budget"]["max_total_tokens_per_trial"] <= 0:
                raise ValueError(f"{item['name']} needs a positive max_total_tokens_per_trial even at zero cost")
        profile = ROOT / item["profile"]
        if not profile.is_file():
            raise ValueError(f"agent profile does not exist: {profile}")
        budget = item.get("budget", {})
        if not isinstance(budget.get("agent_timeout_seconds"), int) or budget["agent_timeout_seconds"] <= 0:
            raise ValueError(f"{item['name']} needs a positive agent_timeout_seconds")
        if not isinstance(budget.get("candidate_timeout_seconds"), (int, float)) or budget["candidate_timeout_seconds"] <= 0:
            raise ValueError(f"{item['name']} needs a positive candidate_timeout_seconds")
    if matrix.get("tasks") != [f"S{i:02}" for i in range(1, 9)]:
        raise ValueError("experiment tasks must be exactly S01 through S08 in order")
    if matrix.get("trials") != [1, 2, 3]:
        raise ValueError("full experiment must use three independent trials numbered 1, 2, 3")
    pilot = matrix.get("pilot", {})
    if pilot.get("tasks") != ["S01", "S05", "S08"] or pilot.get("trial") != 0:
        raise ValueError("pilot must run one independent trial of S01, S05, and S08")
    if matrix.get("comparison_unit") not in ("model", "model-agent configuration"):
        raise ValueError("comparison_unit must explicitly be 'model' or 'model-agent configuration'")
    if matrix.get("comparison_unit") == "model" and len({item["profile"] for item in configs}) != 1:
        raise ValueError("model-only comparisons must use the same agent profile for every configuration")
    return matrix


def plan(matrix: dict, mode: str) -> dict:
    count = len(matrix["configurations"]) * len(matrix["pilot"]["tasks"]) if mode == "pilot" else len(matrix["configurations"]) * len(matrix["tasks"]) * len(matrix["trials"])
    return {
        "mode": mode,
        "planned_trial_count": count,
        "task_scope": matrix["pilot"]["tasks"] if mode == "pilot" else matrix["tasks"],
        "configuration_names": [item["name"] for item in matrix["configurations"]],
        "sandbox_image": SANDBOX_IMAGE,
        "paid_api_calls_started": False,
        "execution_requires_flag": "--execute",
    }


def _require_pilot_review() -> None:
    status_path = ROOT / "results" / "pilot" / "pilot_status.json"
    approval_path = ROOT / "results" / "pilot" / "pilot_approval.json"
    if not status_path.is_file() or json.loads(status_path.read_text()).get("status") != "PILOT_COMPLETE":
        raise RuntimeError("full experiment blocked: complete the three-configuration pilot first")
    if not approval_path.is_file():
        raise RuntimeError(f"full experiment blocked: review pilot transcripts and create {approval_path.relative_to(ROOT)} with approved=true")
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if approval.get("approved") is not True or not approval.get("reviewer") or not approval.get("reviewed_at_utc"):
        raise RuntimeError("full experiment blocked: pilot approval must record approved=true, reviewer, and reviewed_at_utc")


def _completed_triples(results_dir: Path) -> set:
    triples = set()
    for idx_path in sorted(results_dir.glob("runs/*/trial_index.json")):
        try:
            item = json.loads(idx_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        triples.add((item.get("model_id"), item.get("task"), item.get("trial")))
    return triples


def execute(matrix: dict, mode: str, only_config: str | None = None, skip_completed: bool = False) -> dict:
    spend = matrix.get("spend_control", {})
    cap = spend.get("max_total_cost_usd")
    all_zero = len(matrix.get("configurations", [])) == 3 and all(_is_zero_cost(item) for item in matrix["configurations"])
    if all_zero:
        # Explicit zero-spend run: no provider can charge (local models and
        # documented $0/free-tier models only). Caps are exactly zero and the
        # evidence/authorization records must still be present and non-empty.
        if cap != 0:
            raise RuntimeError("zero-cost experiment requires an explicit spend_control.max_total_cost_usd of exactly 0")
        provider_cap = spend.get("provider_hard_spend_limit_usd")
        if provider_cap != 0:
            raise RuntimeError("zero-cost experiment requires provider_hard_spend_limit_usd of exactly 0")
        if not spend.get("provider_hard_spend_limit_evidence") or not spend.get("owner_authorization_record"):
            raise RuntimeError("zero-cost experiment still requires hard-limit evidence and explicit owner authorization")
    else:
        if not isinstance(cap, (int, float)) or isinstance(cap, bool) or cap <= 0:
            raise RuntimeError("paid experiment blocked: set an explicit positive spend_control.max_total_cost_usd")
        if spend.get("provider_hard_spend_limit_configured") is not True:
            raise RuntimeError("paid experiment blocked: enable a provider-side hard spend limit no greater than the registered cap")
        provider_cap = spend.get("provider_hard_spend_limit_usd")
        if not isinstance(provider_cap, (int, float)) or isinstance(provider_cap, bool) or not (0 < provider_cap <= cap):
            raise RuntimeError("paid experiment blocked: provider_hard_spend_limit_usd must be positive and no greater than the registered total cap")
        if not spend.get("provider_hard_spend_limit_evidence") or not spend.get("owner_authorization_record"):
            raise RuntimeError("paid experiment blocked: record provider hard-limit evidence and explicit owner budget authorization")
    trial_count = len(matrix["configurations"]) * len(matrix["pilot"]["tasks"]) if mode == "pilot" else len(matrix["configurations"]) * len(matrix["tasks"]) * len(matrix["trials"])
    reserved_total = 0.0
    for config in matrix["configurations"]:
        budget = config.get("budget", {})
        if _is_zero_cost(config):
            if not isinstance(budget.get("max_total_tokens_per_trial"), int) or isinstance(budget.get("max_total_tokens_per_trial"), bool) or budget["max_total_tokens_per_trial"] <= 0:
                raise RuntimeError(f"paid experiment blocked: {config['name']} needs a positive max_total_tokens_per_trial")
            for key in ("input_usd_per_million_tokens", "output_usd_per_million_tokens"):
                value = budget.get(key)
                if value != 0:
                    raise RuntimeError(f"zero-cost {config['name']} must keep {key} at exactly 0")
            for name in config.get("credential_env", []):
                if not os.environ.get(name):
                    raise RuntimeError(f"zero-cost {config['name']} names credential {name}, but it is missing from the execution environment")
            profile = json.loads((ROOT / config["profile"]).read_text(encoding="utf-8"))
            if not profile.get("structured_stdout_jsonl"):
                raise RuntimeError(f"paid experiment blocked: {config['name']} profile must emit structured stdout usage events")
            continue
        per_run = budget.get("max_cost_per_trial_usd")
        if not isinstance(per_run, (int, float)) or isinstance(per_run, bool) or per_run <= 0:
            raise RuntimeError(f"paid experiment blocked: {config['name']} needs a positive max_cost_per_trial_usd")
        if not isinstance(budget.get("max_total_tokens_per_trial"), int) or isinstance(budget.get("max_total_tokens_per_trial"), bool) or budget["max_total_tokens_per_trial"] <= 0:
            raise RuntimeError(f"paid experiment blocked: {config['name']} needs a positive max_total_tokens_per_trial")
        for key in ("input_usd_per_million_tokens", "output_usd_per_million_tokens"):
            value = budget.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                raise RuntimeError(f"paid experiment blocked: {config['name']} needs a positive, model-specific {key}")
        if not config.get("credential_env"):
            raise RuntimeError(f"paid experiment blocked: {config['name']} needs one dedicated provider credential environment name")
        if any(not os.environ.get(name) for name in config["credential_env"]):
            raise RuntimeError(f"paid experiment blocked: a configured dedicated provider credential is missing for {config['name']}")
        profile = json.loads((ROOT / config["profile"]).read_text(encoding="utf-8"))
        if not profile.get("structured_stdout_jsonl"):
            raise RuntimeError(f"paid experiment blocked: {config['name']} profile must emit structured stdout usage events")
        reserved_total += per_run * (len(matrix["pilot"]["tasks"]) if mode == "pilot" else len(matrix["tasks"]) * len(matrix["trials"]))
    if reserved_total > cap or reserved_total > provider_cap:
        raise RuntimeError("paid experiment blocked: reserved per-trial caps exceed the experiment or provider hard-spend cap")
    sandbox = docker_preflight(SANDBOX_IMAGE)
    if mode == "full":
        _require_pilot_review()
    outputs = []
    if mode == "pilot":
        trial = matrix["pilot"]["trial"]
        for config in matrix["configurations"]:
            budget = config["budget"]
            for task in matrix["pilot"]["tasks"]:
                output_dir = ROOT / "results" / "pilot" / config["name"] / task
                result = run_trial(
                    task, ROOT / config["profile"], config["model_id"], trial,
                    budget["agent_timeout_seconds"], output_dir,
                    candidate_timeout=budget["candidate_timeout_seconds"],
                    trial_configuration={
                        **config, "registered_cost_cap_usd": cap,
                        "provider_hard_spend_limit_usd": provider_cap,
                        "sandbox_preflight": sandbox,
                    },
                )
                outputs.append(result)
                if _trial_budget_breached(result, config):
                    status = {
                        "status": "BUDGET_STOPPED", "trial_count": len(outputs),
                        "reason": "a configured budget limit was exceeded, or provider usage metadata was absent/incomplete for a non-zero-cost trial; no further trials were started",
                        "tasks": matrix["pilot"]["tasks"], "results": outputs,
                    }
                    status_path = ROOT / "results" / "pilot" / "pilot_status.json"
                    status_path.parent.mkdir(parents=True, exist_ok=True)
                    status_path.write_text(json.dumps(status, indent=2, default=str) + "\n", encoding="utf-8")
                    return status
        status = {"status": "PILOT_COMPLETE", "trial_count": len(outputs), "tasks": matrix["pilot"]["tasks"], "results": outputs}
        status_path = ROOT / "results" / "pilot" / "pilot_status.json"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(json.dumps(status, indent=2, default=str) + "\n", encoding="utf-8")
        return status

    done = _completed_triples(ROOT / "results") if skip_completed else set()
    skipped = 0
    for config in matrix["configurations"]:
        if only_config and config["name"] != only_config:
            continue
        budget = config["budget"]
        for task in matrix["tasks"]:
            for trial in matrix["trials"]:
                if skip_completed and (config["model_id"], task, trial) in done:
                    skipped += 1
                    continue
                result = run_trial(
                    task, ROOT / config["profile"], config["model_id"], trial,
                    budget["agent_timeout_seconds"], ROOT / "results",
                    candidate_timeout=budget["candidate_timeout_seconds"],
                    trial_configuration={
                        **config, "registered_cost_cap_usd": cap,
                        "provider_hard_spend_limit_usd": provider_cap,
                        "sandbox_preflight": sandbox,
                    },
                )
                outputs.append(result)
                if result.get("quota_exhausted") and _is_zero_cost(config):
                    path = ROOT / "results" / "experiment_launch.json"
                    stopped = {
                        "status": "QUOTA_EXHAUSTED", "trial_count": len(outputs),
                        "required_trial_count": 72,
                        "reason": "provider free-tier quota exhausted for a zero-cost configuration; further trials would fail without producing evidence, so no further trials were started",
                        "registered_cost_cap_usd": cap, "trials": outputs,
                        "scope": {"only_config": only_config, "skip_completed": skip_completed, "skipped_completed_triples": skipped},
                    }
                    path.write_text(json.dumps(stopped, indent=2, default=str) + "\n", encoding="utf-8")
                    return stopped
                if _trial_budget_breached(result, config):
                    path = ROOT / "results" / "experiment_launch.json"
                    stopped = {
                        "status": "BUDGET_STOPPED", "trial_count": len(outputs),
                        "required_trial_count": 72,
                        "reason": "a configured budget limit was exceeded, or provider usage metadata was absent/incomplete for a non-zero-cost trial; no further trials were started",
                        "registered_cost_cap_usd": cap, "trials": outputs,
                    }
                    path.write_text(json.dumps(stopped, indent=2, default=str) + "\n", encoding="utf-8")
                    return stopped
    status = {"status": "FULL_RUNS_RECORDED", "trial_count": len(outputs), "required_trial_count": 72, "registered_cost_cap_usd": cap, "trials": outputs,
              "scope": {"only_config": only_config, "skip_completed": skip_completed, "skipped_completed_triples": skipped}}
    path = ROOT / "results" / "experiment_launch.json"
    path.write_text(json.dumps(status, indent=2, default=str) + "\n", encoding="utf-8")
    return status


def _trial_budget_breached(result: dict, config: dict) -> bool:
    """Fail closed on real budget breaches; tolerate transient infra errors only at zero cost.

    Any trial with a token/estimated-cost budget stop always halts the run. A trial
    with absent/incomplete usage metadata halts the run unless its configuration is
    a declared zero-cost tier (local models or documented $0 models), where no
    charge is possible by construction and the wall timeout still bounds the
    attempt. Such trials are still recorded with reported:false and graded, so no
    evidence is hidden; the failure analysis must classify them as execution
    failures, not model behavior.
    """
    usage = result.get("usage", {})
    if usage.get("budget_stop_reason"):
        return True
    if not usage.get("reported") or not usage.get("estimated_cost_complete"):
        return not _is_zero_cost(config)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=ROOT / "configs" / "experiment_matrix.json")
    parser.add_argument("--mode", choices=["pilot", "full"], required=True)
    parser.add_argument("--execute", action="store_true", help="explicitly authorize configured agent calls")
    parser.add_argument("--only-config", default=None, help="resume/supplement: run only the named configuration (must exist in the matrix)")
    parser.add_argument("--skip-completed", action="store_true", help="resume/supplement: skip (model,task,trial) triples that already have a trial_index.json under results/runs")
    args = parser.parse_args()
    try:
        matrix = load_matrix(args.matrix.resolve(), require_models=args.execute)
        if args.only_config and args.only_config not in [c["name"] for c in matrix["configurations"]]:
            raise ValueError(f"unknown configuration: {args.only_config}")
        if not args.execute:
            print(json.dumps(plan(matrix, args.mode), indent=2))
            return
        print(json.dumps(execute(matrix, args.mode, only_config=args.only_config, skip_completed=args.skip_completed), indent=2, default=str))
    except Exception as exc:
        print(json.dumps({"status": "NOT_STARTED", "reason": f"{type(exc).__name__}: {exc}"}, indent=2), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
