"""
Rule-based failure detection.

Each detector takes a run's full event list and returns a list of flag
dicts. These are pure functions over data already in Postgres — no LLM
calls, no side effects — which makes them fast, free, and deterministic
(important: you want failure detection itself to never be the flaky part).

Hallucination detection is intentionally NOT here — judging whether a
final answer is factually grounded in tool results requires actual
reasoning, not pattern matching. That's built properly in Milestone 7
using Claude as a judge. A keyword-matching "fake" hallucination detector
would just produce wrong answers, so we don't build one.
"""

import uuid

TOKEN_BLOWOUT_THRESHOLD = 2000   # tokens in a single llm_call
LOOP_REPEAT_THRESHOLD = 3        # identical tool calls before flagging


def detect_infinite_loop(events: list[dict]) -> list[dict]:
    """Flag when the same tool is called with the same input 3+ times in a run."""
    flags = []
    tool_calls = [e for e in events if e["type"] == "tool_call"]

    seen_counts = {}
    for event in tool_calls:
        # input is stored as JSONB -> dict like {"args": [...], "kwargs": {...}}
        key = (event["name"], str(event["input"]))
        seen_counts.setdefault(key, []).append(event)

    for (tool_name, _input_repr), occurrences in seen_counts.items():
        if len(occurrences) >= LOOP_REPEAT_THRESHOLD:
            flags.append({
                "event_id": occurrences[-1]["id"],  # flag the last occurrence
                "flag_type": "infinite_loop",
                "severity": "critical",
                "description": (
                    f"Tool '{tool_name}' was called with identical input "
                    f"{len(occurrences)} times in this run — likely stuck in a loop."
                ),
            })
    return flags


def detect_token_blowout(events: list[dict]) -> list[dict]:
    """Flag any single llm_call whose total tokens exceed the threshold."""
    flags = []
    for event in events:
        if event["type"] != "llm_call":
            continue
        total = (event.get("tokens_in") or 0) + (event.get("tokens_out") or 0)
        if total > TOKEN_BLOWOUT_THRESHOLD:
            flags.append({
                "event_id": event["id"],
                "flag_type": "token_blowout",
                "severity": "warning",
                "description": (
                    f"LLM call used {total} tokens "
                    f"(in={event.get('tokens_in')}, out={event.get('tokens_out')}), "
                    f"exceeding the {TOKEN_BLOWOUT_THRESHOLD} token threshold."
                ),
            })
    return flags


def detect_tool_errors(events: list[dict]) -> list[dict]:
    """Flag any tool_call that errored, or returned an explicit 'not found' result."""
    flags = []
    for event in events:
        if event["type"] != "tool_call":
            continue

        if event.get("error"):
            flags.append({
                "event_id": event["id"],
                "flag_type": "tool_error",
                "severity": "critical",
                "description": f"Tool '{event['name']}' raised an error: {event['error']}",
            })
            continue

        output = event.get("output")
        if isinstance(output, str) and "no results found" in output.lower():
            flags.append({
                "event_id": event["id"],
                "flag_type": "tool_error",
                "severity": "warning",
                "description": (
                    f"Tool '{event['name']}' returned no results for its query "
                    f"— possible retrieval failure."
                ),
            })
    return flags


def run_all_detectors(events: list[dict]) -> list[dict]:
    """Run every detector and return a combined, ready-to-insert flag list."""
    flags = []
    flags += detect_infinite_loop(events)
    flags += detect_token_blowout(events)
    flags += detect_tool_errors(events)

    # attach IDs and run_id is added by the caller before insert
    for flag in flags:
        flag["id"] = str(uuid.uuid4())
    return flags