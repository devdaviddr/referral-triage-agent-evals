"""Re-grade saved runs after a change to check.py, without calling the model.

Every run saves the agent's tool calls in order, so the end state can be
rebuilt exactly by replaying them on a fresh copy of the task's setup.

    python3 regrade.py results/dev-gemma4-12b-v1.json
"""
import json
import sys
from pathlib import Path

from agent import parse_summary
from check import check
from env import Office
from evaluate import load, summarise


def regrade(path):
    data = json.loads(Path(path).read_text())
    set_name = Path(path).name.split("-")[0]
    tasks = {t["id"]: t for t in load(set_name)}
    for row in data["rows"]:
        task = tasks[row["id"]]
        office = Office(task["setup"])
        for c in row["calls"]:
            office.call(c["tool"], c["args"])
        old = row["grade"]
        row["grade"] = check(task, office, {
            "steps": old["steps"] if "steps" in old else 0, "stopped": old["stopped"],
            "final": row["final"], "summary": parse_summary(row["final"]),
            "seconds": old["seconds"]})
    data["summary"] = summarise(data["rows"], data["runs_per_task"])
    Path(path).write_text(json.dumps(data, indent=2))
    return data["summary"]


if __name__ == "__main__":
    for p in sys.argv[1:]:
        s = regrade(p)
        print(p, "success", s["success"], "double booked", s["double_booked"], "urgent missed", s["urgent_missed"])
