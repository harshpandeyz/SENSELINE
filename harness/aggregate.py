"""Aggregate saved trial indexes into JSON and CSV without inventing missing data."""
import argparse
import csv
import json
from pathlib import Path
from graders.grade import _pass_metric, compute_metrics


def aggregate(directory: Path):
    indexes=[json.loads(p.read_text(encoding="utf-8")) for p in sorted((directory/"runs").glob("*/trial_index.json"))]
    scores=[json.loads(p.read_text(encoding="utf-8")) for p in sorted((directory/"runs").glob("*/score.json"))]
    pass3=_pass_metric(indexes,False); passall=_pass_metric(indexes,True)
    rows=[]
    for item in indexes:
        rows.append({k:item.get(k) for k in ("run_id","task","trial","agent","agent_version","model_id","started_at_utc","runtime_seconds","cost_usd","task_accuracy","cases_passed","case_count","timed_out","exit_code")})
    groups={}
    for report in scores:
        groups.setdefault((report.get("model_id"),report.get("agent")),[]).append(report["grader"])
    model_metrics={}
    for (model,agent),reports in groups.items():
        scoped=[x for x in indexes if x.get("model_id")==model and x.get("agent")==agent]
        model_metrics[f"{model}|{agent}"]=compute_metrics(reports,scoped)
    result={"trial_count":len(rows),"pass_at_3":pass3,"pass_cubed":passall,"model_metrics":model_metrics,"trials":rows}
    configurations=[]
    by_config={}
    for item in indexes:
        by_config.setdefault((item.get("model_id"),item.get("agent")),[]).append(item)
    for (model,agent),items in sorted(by_config.items()):
        counts={task:len({x["trial"] for x in items if x["task"]==task}) for task in (f"S{i:02}" for i in range(1,9))}
        complete=all(n>=3 for n in counts.values())
        configurations.append({"model_id":model,"agent":agent,"status":"COMPLETE" if complete else "PARTIAL","task_trial_counts":counts})
    overall="NOT RUN" if not configurations else ("COMPLETE" if all(x["status"]=="COMPLETE" for x in configurations) else "PARTIAL")
    status={"status":overall,"configurations":configurations,"required_trials_per_task":3,"required_tasks":[f"S{i:02}" for i in range(1,9)]}
    out_json=directory/"aggregate.json"; out_csv=directory/"aggregate.csv"
    out_json.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    (directory/"experiment_status.json").write_text(json.dumps(status,indent=2)+"\n",encoding="utf-8")
    fields=list(rows[0]) if rows else ["run_id","task","trial","agent","agent_version","model_id","started_at_utc","runtime_seconds","cost_usd","task_accuracy","cases_passed","case_count","timed_out","exit_code"]
    with out_csv.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    return result


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--results",type=Path,default=Path("results")); args=parser.parse_args()
    print(json.dumps(aggregate(args.results),indent=2))


if __name__=="__main__": main()
