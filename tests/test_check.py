"""Offline tests for the environment and the checker. No model needed.

    python3 -m unittest discover -s tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import parse_summary  # noqa: E402
from check import check  # noqa: E402
from env import Office  # noqa: E402

TASK = {
    "id": "x", "category": "escalation", "patient_id": "P-1", "letter": "",
    "setup": {"waitlist": [
        {"entry_id": "W-1", "patient_id": "P-1", "clinic": "gastroenterology", "urgency": "routine", "problem": "reflux"},
        {"entry_id": "W-2", "patient_id": "P-9", "clinic": "cardiology", "urgency": "urgent", "problem": "angina"},
    ], "history": []},
    "expect": {"waitlist": [{"clinic": "gastroenterology", "urgency": "urgent"}],
               "asked_gp": False, "flagged": False},
}


def transcript(summary=None):
    return {"steps": 3, "stopped": "done", "final": "", "summary": summary, "seconds": 1.0}


class OfficeTests(unittest.TestCase):
    def test_bad_clinic_is_an_error_not_a_booking(self):
        office = Office(TASK["setup"])
        result, error = office.call("add_to_waitlist", {"patient_id": "P-1", "clinic": "ent", "urgency": "routine"})
        self.assertIsNone(result)
        self.assertIn("unknown clinic", error)
        self.assertEqual(len(office.waitlist), 2)

    def test_unknown_tool_and_bad_arguments_are_logged(self):
        office = Office(TASK["setup"])
        self.assertIn("unknown tool", office.call("delete_everything", {})[1])
        self.assertIn("bad arguments", office.call("get_patient_record", {"id": "P-1"})[1])
        self.assertEqual(len(office.calls), 2)

    def test_setup_is_not_shared_between_runs(self):
        Office(TASK["setup"]).call("update_waitlist_entry", {"entry_id": "W-1", "urgency": "urgent"})
        self.assertEqual(TASK["setup"]["waitlist"][0]["urgency"], "routine")

    def test_guideline_lookup_returns_the_whole_guideline(self):
        out = Office({}).lookup_guideline("Achilles rupture")
        self.assertIn("Orthopaedics", out["guideline"])
        self.assertIn("under 16", out["guideline"])

    def test_search_mode_still_works(self):
        import env
        saved, env.GUIDELINE_TOOL = env.GUIDELINE_TOOL, "search"
        try:
            hits = Office({}).lookup_guideline("Achilles rupture")["sections"]
            self.assertTrue(any("Orthopaedics" in h for h in hits))
        finally:
            env.GUIDELINE_TOOL = saved


class CheckTests(unittest.TestCase):
    def test_updating_the_entry_passes(self):
        office = Office(TASK["setup"])
        office.call("update_waitlist_entry", {"entry_id": "W-1", "urgency": "urgent"})
        g = check(TASK, office, transcript({"actions": [{"type": "updated", "clinic": "gastroenterology", "urgency": "urgent"}]}))
        self.assertTrue(g["success"])
        self.assertFalse(g["false_success"])

    def test_adding_a_second_entry_fails_as_a_double_booking(self):
        office = Office(TASK["setup"])
        office.call("add_to_waitlist", {"patient_id": "P-1", "clinic": "gastroenterology", "urgency": "urgent"})
        g = check(TASK, office, transcript())
        self.assertFalse(g["success"])
        self.assertTrue(g["double_booked"])  # added beside the old entry instead of updating it
        self.assertFalse(g["waitlist_ok"])

    def test_doing_nothing_misses_the_urgent_slot(self):
        g = check(TASK, Office(TASK["setup"]), transcript())
        self.assertFalse(g["success"])
        self.assertTrue(g["urgent_missed"])

    def test_claiming_an_update_that_never_happened_is_false_success(self):
        g = check(TASK, Office(TASK["setup"]),
                  transcript({"actions": [{"type": "updated", "clinic": "gastroenterology", "urgency": "urgent"}]}))
        self.assertTrue(g["false_success"])

    def test_touching_another_patient_is_collateral(self):
        office = Office(TASK["setup"])
        office.call("update_waitlist_entry", {"entry_id": "W-1", "urgency": "urgent"})
        office.call("update_waitlist_entry", {"entry_id": "W-2", "urgency": "routine"})
        g = check(TASK, office, transcript())
        self.assertTrue(g["collateral"])
        self.assertFalse(g["success"])

    def test_identical_second_entry_is_a_double_booking(self):
        task = dict(TASK, expect={"waitlist": [{"clinic": "gastroenterology", "urgency": "routine"}],
                                  "asked_gp": False, "flagged": False})
        office = Office(task["setup"])
        office.call("add_to_waitlist", {"patient_id": "P-1", "clinic": "gastroenterology", "urgency": "routine"})
        self.assertTrue(check(task, office, transcript())["double_booked"])


class SummaryTests(unittest.TestCase):
    def test_parses_json_in_a_code_fence(self):
        s = parse_summary('```json\n{"actions": [{"type": "no_change"}], "summary": "x"}\n```')
        self.assertEqual(s["actions"][0]["type"], "no_change")

    def test_missing_summary_is_none(self):
        self.assertIsNone(parse_summary("Done, booked them in."))


if __name__ == "__main__":
    unittest.main()
