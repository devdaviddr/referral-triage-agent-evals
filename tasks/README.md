# Tasks

50 synthetic referral scenarios plus a fresh set of 20, each with a starting state and the end state the agent must leave behind. No real patients: every name and detail is invented. See [FORMAT.md](FORMAT.md) for the schema.

## Files

| File | Tasks | Used for |
| --- | --- | --- |
| `dev.jsonl` | 30 | Tuning the prompt and tools |
| `test.jsonl` | 20 | First held-out set. Its failures were later used to diagnose v4, so v4's score on it is a check, not a clean held-out measure |
| `test2.jsonl` | 20 | Fresh held-out set, written after v3, never used for tuning. About half the letters are about conditions the guideline doesn't name |

## Categories

Each file follows the same mix:

| Category | What the agent has to get right |
| --- | --- |
| `simple` | Book the right clinic at the right urgency |
| `buried_red_flag` | Spot a red flag in the middle of an ordinary letter and book urgent |
| `time_critical` | Book recent tendon ruptures and similar injuries as urgent, but not chronic look-alikes |
| `duplicate` | Patient already listed for the same problem: add nothing |
| `escalation` | Patient already listed and getting worse: raise the existing entry, don't add a second |
| `downgrade_request` | GP says things improved: never lower the entry, flag it instead |
| `missing_info` | Too little detail to triage: ask the GP, don't book |
| `out_of_scope` | A service this clinic doesn't run, including patients under 16: flag, don't book |
| `two_problems` | Two problems in one letter: book each, or book one and flag the other |
| `gp_request_conflict` | The GP's requested urgency doesn't match the clinical details: go by the details |

Every task also puts one or two other patients on the waitlist, so any change to someone else's record is caught.

## How the tasks were made

A different model from the one under test (Claude) wrote the tasks and their expected outcomes from [guidelines.md](../guidelines.md). No clinician reviewed them. Where the guideline doesn't require a flag or a question to the GP, the task allows either, so extra caution isn't marked wrong.
