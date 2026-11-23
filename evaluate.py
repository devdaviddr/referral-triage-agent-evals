"""Run the agent on every task several times and score the results.

    python3 evaluate.py --prompt v1 --set dev
    python3 evaluate.py --prompt v1 --set dev --runs 1 --limit 3     # quick smoke test
    python3 evaluate.py --compare results/dev-gemma4-12b-v1.json results/dev-gemma4-12b-v2.json

Each task runs --runs times (default 3) at temperature 0.6, because an agent
that passes once and fails the next time can't be relied on. Results are
saved to results/<set>-<model>-<prompt>.json with every tool call, so runs
can be compared and inspected later without the model.
"""
import argparse
import json
import os
import time
from collections import defaultdict
from pathlib import Path

import agent
from check import check

HERE = Path(__file__).parent
RATES = ["success", "urgent_missed", "double_booked", "collateral", "false_success", "no_summary"]


def load(name):
    return [json.loads(line) for line in (HERE / "tasks" / f"{name}.jsonl").open()]


def summarise(rows, runs):
    n = len(rows)
    by_task = defaultdict(list)
    for r in rows:
        by_task[r["id"]].append(r["grade"]["success"])
    out = {"runs": n, "tasks": len(by_task)}
    for k in RATES:
        out[k] = round(sum(r["grade"][k] for r in rows) / n, 3)
    out["pass_every_run"] = round(sum(all(v) for v in by_task.values()) / len(by_task), 3)
    out["pass_any_run"] = round(sum(any(v) for v in by_task.values()) / len(by_task), 3)
    out["mean_tool_calls"] = round(sum(r["grade"]["tool_calls"] for r in rows) / n, 2)
    out["tool_error_rate"] = round(sum(r["grade"]["tool_errors"] for r in rows) /
                                   max(sum(r["grade"]["tool_calls"] for r in rows), 1), 3)
    out["checked_record"] = round(sum(r["grade"]["checked_record"] for r in rows) / n, 3)
    out["looked_up_guideline"] = round(sum(r["grade"]["looked_up_guideline"] for r in rows) / n, 3)
    out["hit_step_limit"] = sum(r["grade"]["stopped"] == "step_limit" for r in rows)
    out["median_seconds"] = sorted(r["grade"]["seconds"] for r in rows)[n // 2]
    cats = defaultdict(list)
    for r in rows:
        cats[r["category"]].append(r["grade"]["success"])
    out["by_category"] = {c: f"{sum(v)}/{len(v)}" for c, v in sorted(cats.items())}
    return out


def show(name, s):
    print(f"\n== {name}  ({s['tasks']} tasks x {s['runs'] // s['tasks']} runs)")
    print(f"success {s['success']:.0%}  pass every run {s['pass_every_run']:.0%}  "
          f"pass any run {s['pass_any_run']:.0%}")
    print(f"urgent missed {s['urgent_missed']:.0%}  double booked {s['double_booked']:.0%}  "
          f"collateral {s['collateral']:.0%}  false success {s['false_success']:.0%}  "
          f"no summary {s['no_summary']:.0%}")
    print(f"tool calls {s['mean_tool_calls']}  tool errors {s['tool_error_rate']:.0%}  "
          f"checked record {s['checked_record']:.0%}  used guideline {s['looked_up_guideline']:.0%}  "
          f"step limit {s['hit_step_limit']}  median {s['median_seconds']}s")
    print("by category: " + "  ".join(f"{c} {v}" for c, v in s["by_category"].items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="v1")
    ap.add_argument("--set", default="dev")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.6)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--compare", nargs="+")
    a = ap.parse_args()

    if a.compare:
        for f in a.compare:
            show(Path(f).stem, json.loads(Path(f).read_text())["summary"])
        return

    tasks = load(a.set)[: a.limit]
    rows, t0 = [], time.time()
    for task in tasks:
        for i in range(a.runs):
            try:
                office, tr = agent.run(task, prompt=a.prompt, temperature=a.temperature)
                grade = check(task, office, tr)
                calls, final = office.calls, tr["final"]
            except Exception as e:  # a crashed run is a failed run
                grade = {k: False for k in RATES} | {"success": False, "no_summary": True,
                         "tool_calls": 0, "tool_errors": 0, "checked_record": False,
                         "looked_up_guideline": False, "stopped": f"crash: {e}", "seconds": 0,
                         "false_claims": []}
                calls, final = [], ""
            rows.append({"id": task["id"], "run": i, "category": task["category"],
                         "grade": grade, "calls": calls, "final": final})
            mark = "ok " if grade["success"] else "FAIL"
            print(f"{task['id']} run {i} {mark} {grade.get('false_claims') or ''}", flush=True)

    model = agent.MODEL.replace(":", "-").replace("/", "-")
    tool = os.environ.get("GUIDELINE_TOOL", "full")
    name = f"{a.set}-{model}-{a.prompt}" + ("" if tool == "full" else f"-{tool}")
    s = summarise(rows, a.runs)
    (HERE / "results" / f"{name}.json").write_text(json.dumps(
        {"name": name, "model": model, "prompt": a.prompt, "guideline_tool": tool, "runs_per_task": a.runs,
         "temperature": a.temperature, "wall_seconds": round(time.time() - t0, 1),
         "summary": s, "rows": rows}, indent=2))
    show(name, s)


if __name__ == "__main__":
    main()
