"""The referral triage agent: a plain tool-calling loop.

The model reads one referral, calls tools until it's done, then replies
with a JSON summary of what it did. That summary is what the checker
compares with the real end state to catch false claims of success.

    LLM_BASE_URL   default http://127.0.0.1:11434/v1 (Ollama)
    LLM_MODEL      default gemma4:12b
    LLM_API_KEY    optional bearer token
"""
import json
import os
import re
import time
import urllib.request
from pathlib import Path

from env import TOOLS, Office

BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:11434/v1")
MODEL = os.environ.get("LLM_MODEL", "gemma4:12b")
API_KEY = os.environ.get("LLM_API_KEY", "")
PROMPTS = Path(__file__).parent / "prompts"
MAX_STEPS = 12


def chat(messages, temperature):
    body = {"model": MODEL, "messages": messages, "tools": TOOLS,
            "temperature": temperature, "max_tokens": 800, "reasoning_effort": "none"}
    req = urllib.request.Request(
        BASE_URL.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {API_KEY}"} if API_KEY else {})})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)["choices"][0]["message"]


def parse_summary(text):
    """The agent's final JSON summary, or None if it didn't give one."""
    m = re.search(r"\{.*\}", text or "", flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def run(task, prompt="v1", temperature=0.0):
    """Run the agent on one task. Returns the office (end state) and a transcript."""
    office = Office(task["setup"])
    messages = [
        {"role": "system", "content": (PROMPTS / f"{prompt}.txt").read_text()},
        {"role": "user", "content": f"Patient ID: {task['patient_id']}\n\nReferral letter:\n{task['letter']}"},
    ]
    t, steps, final, stopped = time.time(), 0, "", "done"
    while True:
        if steps >= MAX_STEPS:
            stopped = "step_limit"
            break
        msg = chat(messages, temperature)
        steps += 1
        calls = msg.get("tool_calls") or []
        if not calls:
            final = msg.get("content") or ""
            break
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for c in calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result, error = office.call(name, args)
            messages.append({"role": "tool", "tool_call_id": c.get("id", ""),
                             "content": json.dumps({"error": error} if error else result)})
    return office, {"steps": steps, "stopped": stopped, "final": final,
                    "summary": parse_summary(final), "seconds": round(time.time() - t, 1)}
