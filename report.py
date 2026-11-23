"""Rebuild the published results tables from the saved runs in results/.

Every number in the article and the README comes from here, so they can be
checked without calling a model.

    python3 report.py
"""
import json
from pathlib import Path

RESULTS = Path(__file__).parent / "results"
MODEL = "gemma4-12b"

SETS = [
    ("dev", "30 tuning tasks", ["v1", "v2", "v3", "v4"]),
    ("test", "First held-out set, 20 tasks", ["v1", "v3", "v4"]),
    ("test2", "Fresh held-out set, 20 tasks", ["v1", "v3-search", "v3", "v4"]),
]


def load(set_name, version):
    path = RESULTS / f"{set_name}-{MODEL}-{version}.json"
    return json.loads(path.read_text()) if path.exists() else None


def pct(x):
    return f"{x:.0%}"


def table(header, rows):
    print("| " + " | ".join(header) + " |")
    print("|" + " --- |" * len(header))
    for r in rows:
        print("| " + " | ".join(str(c) for c in r) + " |")
    print()


def main():
    total_runs = false_claims = 0
    for set_name, label, versions in SETS:
        rows = []
        for v in versions:
            d = load(set_name, v)
            if not d:
                continue
            s = d["summary"]
            total_runs += s["runs"]
            false_claims += sum(r["grade"]["false_success"] for r in d["rows"])
            prompt = v.split("-")[0]
            tool = "keyword search" if d.get("guideline_tool", "full") == "search" else "whole guideline"
            rows.append((prompt, tool, pct(s["success"]), pct(s["pass_every_run"]),
                         pct(s["urgent_missed"]), s["mean_tool_calls"], s["hit_step_limit"]))
        print(f"{label} (3 runs per task)\n")
        table(["Prompt", "Guideline tool", "Successful runs", "Tasks passing every run",
               "Urgent patient left unbooked", "Tool calls per task", "Runs that hit the step limit"], rows)

    print("By category, fresh held-out set\n")
    cats = None
    rows = []
    for v in ["v1", "v3-search", "v4"]:
        d = load("test2", v)
        if d:
            cats = cats or list(d["summary"]["by_category"])
            rows.append([v] + [d["summary"]["by_category"][c] for c in cats])
    if cats:
        table(["Version"] + cats, rows)

    print(f"Across all {total_runs} saved runs, the agent's summary claimed an action the "
          f"end state didn't back up {false_claims} times.")


if __name__ == "__main__":
    main()
