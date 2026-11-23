#!/bin/sh
# Re-run every eval behind the article, in order. Needs Ollama with
# gemma4:12b pulled. About 6.5 hours on a 16 GB Mac mini: 780 agent runs at
# roughly 30 seconds each. Run one at a time; Ollama serves one request at a
# time, so overlapping runs slow each other down.
#
# Two things changed between versions besides the prompt, as in the article:
# before v3 the guideline gained a line on disabling osteoarthritis, and
# before v4 it gained the under-16 rule and the tool switched from keyword
# search to returning the whole guideline (GUIDELINE_TOOL). Re-running the
# early versions here uses the current guideline text.
set -e
cd "$(dirname "$0")"
export LLM_MODEL=gemma4:12b

# 1. Tuning set, with the original keyword-search tool for v1 to v3
for p in v1 v2 v3; do GUIDELINE_TOOL=search python3 evaluate.py --prompt $p --set dev; done
python3 evaluate.py --prompt v4 --set dev

# 2. First held-out set
for p in v1 v3; do GUIDELINE_TOOL=search python3 evaluate.py --prompt $p --set test; done
python3 evaluate.py --prompt v4 --set test

# 3. Fresh held-out set, all with the whole-guideline tool, plus v3 with search for comparison
for p in v1 v3 v4; do python3 evaluate.py --prompt $p --set test2; done
GUIDELINE_TOOL=search python3 evaluate.py --prompt v3 --set test2

python3 report.py
