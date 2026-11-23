# Task format

Each line of `tasks/*.jsonl` is one task: a starting state, a referral for one patient, and the end state the agent must leave behind.

```json
{
  "id": "t-001",
  "category": "duplicate",
  "patient_id": "P-001",
  "letter": "Dear Dr, ...",
  "setup": {
    "waitlist": [
      {"entry_id": "W-001", "patient_id": "P-001", "clinic": "orthopaedics", "urgency": "routine", "problem": "right knee osteoarthritis"},
      {"entry_id": "W-002", "patient_id": "P-900", "clinic": "cardiology", "urgency": "urgent", "problem": "exertional chest pain"}
    ],
    "history": [
      {"patient_id": "P-001", "note": "Seen in orthopaedics 2023 for right knee osteoarthritis, discharged to GP."}
    ]
  },
  "expect": {
    "waitlist": [
      {"clinic": "orthopaedics", "urgency": "routine"}
    ],
    "asked_gp": false,
    "flagged": false
  },
  "note": "Same problem already on the routine list with no change; adding a second entry would be a double booking."
}
```

## Fields

- `category`: one of `simple`, `buried_red_flag`, `time_critical`, `duplicate`, `escalation`, `downgrade_request`, `missing_info`, `out_of_scope`, `two_problems`, `gp_request_conflict`.
- `setup.waitlist`: every active waitlist entry before the agent starts, for this patient and for other patients. Entries for other patients must survive unchanged.
- `setup.history`: free-text notes returned by the patient record tool.
- `expect.waitlist`: the exact set of active waitlist entries this patient must have at the end, as clinic and urgency pairs. An empty list means the patient must not be on any waitlist. Duplicates count as wrong.
- `expect.asked_gp`: `true` if the agent must request more information from the GP, otherwise `null` (either is fine). The booking check already catches an agent that asks instead of booking.
- `expect.flagged`: `true` where the guideline requires a flag for clinician review, otherwise `null`. Extra caution is not marked wrong.
- `note`: one sentence explaining the expected outcome.

Clinics: cardiology, orthopaedics, neurology, gastroenterology, dermatology, respiratory. Urgency: urgent, semi-urgent, routine.
