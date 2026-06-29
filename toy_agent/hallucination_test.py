"""
Deliberately constructs a run where the final answer contradicts the real
tool results, to prove the hallucination judge actually catches it.
This bypasses the real LLM loop entirely -- we're testing the judge, not
the agent's tendency to hallucinate (which is non-deterministic and a bad
thing to depend on for a repeatable test).
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from agentops_sdk import start_run, end_run
from agentops_sdk.tracer import _record_event
import time

start_run(name="hallucination_test")

# Real tool call with a real, true result.
_record_event(
    event_type="tool_call", name="search",
    input_data={"args": ["speed of light"], "kwargs": {}},
    output_data="299,792,458 meters per second",
    start_time=time.time(), end_time=time.time(),
)

# Fabricated final answer that contradicts the tool result above --
# states a wrong number that was never returned by any tool.
_record_event(
    event_type="llm_call", name="claude-sonnet-4-6",
    input_data={"messages": []},
    output_data=[{"type": "text", "text": "The speed of light is 150,000,000 meters per second.", "tool_name": None, "tool_input": None}],
    start_time=time.time(), end_time=time.time(),
    tokens_in=50, tokens_out=20,
)

trace = end_run()
print(f"\nRun ID to judge: {trace['run_id']}")