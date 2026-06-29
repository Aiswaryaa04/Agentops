from dotenv import load_dotenv
load_dotenv()

"""
Deliberately broken agent run, used only to prove failure detection works.

This bypasses the LLM entirely and calls tools directly in patterns that
should trigger our detectors — useful because it's free (no API calls) and
100% deterministic, unlike waiting for a real LLM to misbehave on its own.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from agentops_sdk import start_run, end_run
from tools import calculator, search

start_run(name="broken_run_demo")

# 1. Trigger infinite_loop detector: call the same tool with the same input
#    LOOP_REPEAT_THRESHOLD (3) or more times.
for _ in range(4):
    calculator("1 + 1")

# 2. Trigger tool_error detector: search for something not in the knowledge base.
search("capital of mars")

trace = end_run()
print(f"\nRun ID for analysis: {trace['run_id']}")