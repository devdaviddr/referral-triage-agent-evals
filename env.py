"""The agent's world: a referral office with waitlists, patient records and
an outbox. Each task starts from a fresh copy, and every tool call is logged
so the checker can see what the agent actually did.

Standard library only.
"""
import copy
import itertools
import os
import re
from pathlib import Path

CLINICS = ["cardiology", "orthopaedics", "neurology",
           "gastroenterology", "dermatology", "respiratory"]
URGENCIES = ["urgent", "semi-urgent", "routine"]
RANK = {"urgent": 0, "semi-urgent": 1, "routine": 2}

GUIDELINE = (Path(__file__).parent / "guidelines.md").read_text()
GUIDELINE_TOOL = os.environ.get("GUIDELINE_TOOL", "full")  # "full" or "search"


class ToolError(Exception):
    """A bad tool call. The message goes back to the agent, as a real API would."""


class Office:
    def __init__(self, setup):
        self.waitlist = copy.deepcopy(setup.get("waitlist", []))
        self.history = copy.deepcopy(setup.get("history", []))
        self.messages = []   # requests for information sent to GPs
        self.flags = []      # referrals flagged for clinician review
        self.calls = []      # every tool call, in order
        self._ids = itertools.count(1)

    # ---- tools ---------------------------------------------------------

    def get_patient_record(self, patient_id):
        return {
            "patient_id": patient_id,
            "waitlist": [e for e in self.waitlist if e["patient_id"] == patient_id],
            "history": [h["note"] for h in self.history if h["patient_id"] == patient_id],
        }

    def lookup_guideline(self, topic=""):
        """Return the guideline. By default the whole document; with
        GUIDELINE_TOOL=search, only the sections matching the topic's words
        (the original tool, which missed rules worded differently from the
        query and gave nothing for conditions the guideline doesn't name)."""
        if GUIDELINE_TOOL == "full":
            return {"guideline": GUIDELINE,
                    "note": "This is the whole guideline. If it doesn't name the condition, "
                            "set the category from the definitions under Categories."}
        words = [w for w in re.findall(r"[a-z]+", topic.lower()) if len(w) > 3]
        sections = re.split(r"\n(?=#{2,3} )", GUIDELINE)
        hits = [s.strip() for s in sections if any(w in s.lower() for w in words)]
        return {"sections": hits[:4] or ["No matching section. Try a clinic name or a word like 'duplicate'."]}

    def add_to_waitlist(self, patient_id, clinic, urgency, reason=""):
        self._check(clinic=clinic, urgency=urgency)
        entry = {"entry_id": f"N-{next(self._ids):03d}", "patient_id": patient_id,
                 "clinic": clinic, "urgency": urgency, "problem": reason}
        self.waitlist.append(entry)
        return {"ok": True, "entry_id": entry["entry_id"]}

    def update_waitlist_entry(self, entry_id, urgency, reason=""):
        self._check(urgency=urgency)
        for e in self.waitlist:
            if e["entry_id"] == entry_id:
                e["urgency"] = urgency
                return {"ok": True, "entry_id": entry_id, "urgency": urgency}
        raise ToolError(f"no waitlist entry {entry_id}")

    def request_information(self, patient_id, question):
        self.messages.append({"patient_id": patient_id, "question": question})
        return {"ok": True, "sent_to": "referring GP"}

    def flag_for_review(self, patient_id, reason):
        self.flags.append({"patient_id": patient_id, "reason": reason})
        return {"ok": True}

    # ---- plumbing ------------------------------------------------------

    def _check(self, clinic=None, urgency=None):
        if clinic is not None and clinic not in CLINICS:
            raise ToolError(f"unknown clinic {clinic!r}; this service runs: {', '.join(CLINICS)}")
        if urgency is not None and urgency not in URGENCIES:
            raise ToolError(f"unknown urgency {urgency!r}; use one of: {', '.join(URGENCIES)}")

    def call(self, name, args):
        """Run one tool call and log it. Returns (result, error)."""
        fn = getattr(self, name, None) if name in TOOL_NAMES else None
        try:
            if fn is None:
                raise ToolError(f"unknown tool {name!r}")
            result, error = fn(**args), None
        except ToolError as e:
            result, error = None, str(e)
        except TypeError as e:  # missing or unexpected arguments
            result, error = None, f"bad arguments: {e}"
        self.calls.append({"tool": name, "args": args, "error": error})
        return result, error


def _fn(name, description, props, required):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": props, "required": required}}}


_S = {"type": "string"}
TOOLS = [
    _fn("get_patient_record", "Get the patient's current waitlist entries and past referral notes.",
        {"patient_id": _S}, ["patient_id"]),
    _fn("lookup_guideline",
        "Read the referral triage guideline." if GUIDELINE_TOOL == "full"
        else "Search the referral triage guideline. Pass a clinic name, condition or topic.",
        {"topic": _S}, [] if GUIDELINE_TOOL == "full" else ["topic"]),
    _fn("add_to_waitlist", "Add the patient to a clinic waitlist at an urgency category.",
        {"patient_id": _S, "clinic": {"type": "string", "enum": CLINICS},
         "urgency": {"type": "string", "enum": URGENCIES}, "reason": _S},
        ["patient_id", "clinic", "urgency"]),
    _fn("update_waitlist_entry", "Change the urgency of an existing waitlist entry.",
        {"entry_id": _S, "urgency": {"type": "string", "enum": URGENCIES}, "reason": _S},
        ["entry_id", "urgency"]),
    _fn("request_information", "Send the referring GP a request for missing information.",
        {"patient_id": _S, "question": _S}, ["patient_id", "question"]),
    _fn("flag_for_review", "Flag the referral for a clinician to review.",
        {"patient_id": _S, "reason": _S}, ["patient_id", "reason"]),
]
TOOL_NAMES = {t["function"]["name"] for t in TOOLS}
