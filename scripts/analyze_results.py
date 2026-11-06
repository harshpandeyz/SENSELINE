"""Analyze SENSELINE trial records with strict eligibility classification.

Trial classes (never conflated):
  INFRA        - provider/launch failure: usage not reported, or setup blocked,
                 or a recorded provider-resolution error with no candidate attempt.
  TOOL_USE     - agent ran (usage reported) but never produced an implementation:
                 candidate snapshot missing/empty/starter (NotImplementedError).
  GENUINE      - agent produced candidate code that was graded.

Model metrics (SCR, UAR, accuracy, pass@3/pass^3, ...) are computed ONLY over
GENUINE trials. INFRA and BUDGET_BREACH trials are excluded from every model
numerator and denominator. TOOL_USE trials are reported as a separate behavioral rate.
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from graders.grade import compute_metrics


def _is_starter(src: str) -> bool:
    text = src or ""
    if len(text.strip()) == 0:
        return True
    return "NotImplementedError" in text and len(text) < 2000


def classify(index: dict, transcript: dict, trial_dir=None) -> tuple[str, str]:
    """One defensible status per trial, generated from raw evidence.

    BUDGET_BREACH: the budget enforcer terminated the agent (token/cost cap hit,
    exit before completion). The snapshot may still grade, but the trial did not
    execute under its registered budget, so it is excluded from primary metrics
    and reported as a budget finding with evidence preserved.
    INFRA: provider/launch failure with no usage metadata (or a quota block before
    any implementation).
    TOOL_USE: agent ran with reported usage but produced no implementation.
    GENUINE: candidate code was produced and Docker-graded.
    """
    usage = index.get("usage", {}) or transcript.get("usage", {}) or {}
    stop = usage.get("budget_stop_reason")
    if stop and stop != "not_monitored":
        return "BUDGET_BREACH", "budget enforcer stopped the agent at %s tokens (%s); work cut off before completion" % (
            usage.get("total_tokens"), stop)
    if index.get("candidate_source_snapshot_issue"):
        if not usage.get("reported"):
            return "INFRA", "no usage metadata and no candidate snapshot (%s)" % index.get("candidate_source_snapshot_issue")
    stdout = transcript.get("agent_stdout", "") or ""
    if not usage.get("reported"):
        if '"type":"error"' in stdout and ("no-route" in stdout or "Model unavailable" in stdout or "rate-limit" in stdout.lower() or "rate_limit" in stdout.lower()):
            return "INFRA", "provider resolution/rate-limit error with no usage metadata"
        return "INFRA", "usage metadata absent (provider or launch failure)"
    src = ""
    candidates = []
    if trial_dir is not None:
        candidates.append(Path(str(trial_dir)) / "workspace" / "solution.py")
    workspace = index.get("workspace_path")
    if workspace:
        candidates.append(Path(str(workspace)) / "solution.py")
    for sol in candidates:
        if sol.is_file():
            try:
                src = sol.read_text(encoding="utf-8", errors="replace")
            except OSError:
                src = ""
            break
    if _is_starter(src):
        # A quota-blocked trial that never produced code is a provider failure,
        # not an agent tool-use failure (a graded implementation may still exist
        # when the quota flag fired after the solution was written).
        from harness.run_trial import _quota_exhausted_signal
        if _quota_exhausted_signal(transcript.get("agent_stdout", "")):
            return "INFRA", "provider quota exhausted before any implementation was produced"
        return "TOOL_USE", "usage reported but solution.py is starter/empty/missing"
    return "GENUINE", "candidate code produced and graded"


def load_trials(results_dir: Path):
    out = []
    for idx_path in sorted(results_dir.rglob("runs/*/trial_index.json")):
        index = json.loads(idx_path.read_text(encoding="utf-8"))
        score_path = idx_path.parent / "score.json"
        transcript_path = idx_path.parent / "transcript.json"
        if not score_path.is_file() or not transcript_path.is_file():
            continue
        score = json.loads(score_path.read_text(encoding="utf-8"))
        transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
        cls, reason = classify(index, transcript, idx_path.parent)
        parts = set(idx_path.parts)
        if "supplementary" in parts:
            phase = "supplementary"
        elif "pilot-history" in parts:
            phase = "pilot-history"
        elif "pilot" in parts:
            phase = "pilot"
        else:
            phase = "full"
        out.append({"index": index, "score": score, "class": cls, "reason": reason, "phase": phase})
    return out


def summarize(trials):
    by_class = defaultdict(int)
    for t in trials:
        by_class[t["class"]] += 1
    genuine = [t for t in trials if t["class"] == "GENUINE"]
    reports = [t["score"]["grader"] for t in genuine]
    indexes = [t["index"] for t in genuine]
    metrics = compute_metrics(reports, indexes) if reports else None
    per_model = {}
    for (phase, model, agent), group in _group(trials, lambda t: (t.get("phase"), t["index"].get("model_id"), t["index"].get("agent"))).items():
        g = [t for t in group if t["class"] == "GENUINE"]
        reps = [t["score"]["grader"] for t in g]
        idxs = [t["index"] for t in g]
        per_model[f"{phase}|{model}|{agent}"] = {
            "trial_classes": {c: sum(1 for t in group if t["class"] == c) for c in ("GENUINE", "TOOL_USE", "INFRA", "BUDGET_BREACH")},
            "metrics": compute_metrics(reps, idxs) if reps else None,
        }
    return {"trial_class_counts": dict(by_class), "overall_genuine_metrics": metrics, "per_model": per_model}


def _group(trials, key):
    groups = defaultdict(list)
    for t in trials:
        groups[key(t)].append(t)
    return groups


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "experiment_analysis.json")
    args = parser.parse_args()
    trials = load_trials(args.results)
    summary = summarize(trials)
    rows = []
    for t in trials:
        i = t["index"]
        rows.append({
            "phase": t.get("phase"), "model_id": i.get("model_id"), "task": i.get("task"), "trial": i.get("trial"),
            "class": t["class"], "reason": t["reason"],
            "task_accuracy": i.get("task_accuracy"),
            "cases_passed": i.get("cases_passed"), "case_count": i.get("case_count"),
            "runtime_seconds": round(i.get("runtime_seconds", 0) or 0, 1),
            "total_tokens": (i.get("usage", {}) or {}).get("total_tokens"),
            "usage_reported": (i.get("usage", {}) or {}).get("reported"),
            "candidate_sha256": i.get("candidate_source_sha256"),
            "run_id": i.get("run_id"),
        })
    from collections import Counter as _Counter
    phase_counts = _Counter((t.get("phase"), t["class"]) for t in trials)
    output = {
        "trial_count": len(trials),
        "eligible_model_trial_count": summary["trial_class_counts"].get("GENUINE", 0),
        "trial_class_counts": summary["trial_class_counts"],
        "phase_class_counts": {f"{phase}/{cls}": count for (phase, cls), count in sorted(phase_counts.items())},
        "overall_genuine_metrics": summary["overall_genuine_metrics"],
        "per_model": summary["per_model"],
        "trials": rows,
        "method_note": (
            "Canonical eligibility-aware analysis generated from raw trial records "
            "(results/runs, results/pilot, results/pilot-history, results/supplementary). "
            "Every metric reports numerator/denominator/value; denominators are pooled genuine hidden cases. "
            "Eligible trial count: GENUINE only (candidate code produced and Docker-graded under its registered "
            "900 s / 120000-token budget). Included phases: full + pilot + pilot-history + supplementary pooled for "
            "overall_genuine_metrics; per_model splits by phase|model|agent. Excluded from every model numerator/denominator: "
            "INFRA (provider/launch failure, no usable candidate), TOOL_USE (agent ran with usage but starter/empty solution.py; "
            "behavioral evidence, never a reasoning score), BUDGET_BREACH (budget enforcer cut the agent off mid-work, e.g. "
            "82740 and 64271 tokens on 60k budgets; evidence preserved, reported separately). "
            "SCR = corrupted genuine cases / evaluated genuine cases (wrong/incompatible value claimed valid or ACCEPT; "
            "missing-unit-only and harmless schema-only failures excluded). UAR = ACCEPT on non-ACCEPT S06/S08 genuine cases / "
            "all non-ACCEPT S06/S08 genuine cases (zero denominator -> null). pass@3 (any-of-3 perfect) and pass^3 (all-3 perfect) "
            "require >=3 genuine trials per (model, agent, task); groups with fewer contribute 0/0. Numerical errors grouped by "
            "task/field/unit, never pooled across incompatible dimensions."
        ),
    }
    args.out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    csv_path = args.out.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["model_id"])
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"trial_count": len(trials), "classes": summary["trial_class_counts"], "out": str(args.out)}, indent=2))


if __name__ == "__main__":
    main()
