"""Copy only agent-visible task files into an isolated workspace."""
import argparse
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VISIBLE=("task.md","input.schema.json","output.schema.json","public_examples.json","solution.py")


def export_task(task: str, target: Path) -> Path:
    source=next((p for p in (ROOT/"tasks").iterdir() if p.is_dir() and p.name.startswith(task+"_")),None)
    if source is None: raise ValueError(f"unknown task: {task}")
    target=target.resolve()
    if target.exists() and any(target.iterdir()): raise FileExistsError(f"refusing to export into nonempty directory: {target}")
    target.mkdir(parents=True,exist_ok=True)
    for name in VISIBLE: shutil.copy2(source/name,target/name)
    (target/"AGENT_README.md").write_text("Implement solve(payload) in solution.py. The task statement, JSON schemas, and public examples are the complete visible task context.\n",encoding="utf-8")
    return target


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task",choices=[f"S{i:02}" for i in range(1,9)])
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    print(export_task(args.task,args.output))


if __name__=="__main__": main()
