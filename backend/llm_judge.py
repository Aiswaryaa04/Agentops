"""
LLM-as-judge: uses Claude itself to evaluate whether an agent's final
answer is grounded in the tool results it actually retrieved during the
run, and to compare two runs for prompt-version regression.

Unlike the rule-based detectors in failure_detection.py, this:
  - costs real API tokens (a judge call per analysis)
  - is not perfectly deterministic (the judge's wording can vary slightly
    between calls, though its yes/no verdict is generally stable for
    clear-cut cases)
These tradeoffs are why we don't run this automatically on every /analyze
call — it's a separate, deliberate, billable action.
"""

import os
import json
from anthropic import Anthropic

JUDGE_MODEL = "claude-sonnet-4-6"

_client = None


def _get_client():
    """Lazily create the Anthropic client on first use, not at import time --
    so a missing API key only breaks judge calls, not the entire server."""
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _extract_tool_results_and_final_answer(events: list[dict]):
    """
    Pulls out everything the judge needs from a run's events:
      - every tool call's actual output (the "ground truth" the agent had access to)
      - the agent's final text answer (the last llm_call's text content)
    """
    tool_results = []
    for event in events:
        if event["type"] == "tool_call":
            tool_results.append({"tool": event["name"], "result": event["output"]})

    final_answer = None
    for event in reversed(events):
        if event["type"] == "llm_call":
            output = event.get("output") or []
            text_blocks = [b["text"] for b in output if b.get("type") == "text" and b.get("text")]
            if text_blocks:
                final_answer = " ".join(text_blocks)
                break

    return tool_results, final_answer


def judge_hallucination(events: list[dict]) -> dict:
    """
    Returns:
      {
        "is_hallucination": bool,
        "confidence": "high" | "medium" | "low",
        "reasoning": str,
        "final_answer": str,
        "tool_results": [...],
      }
    """
    tool_results, final_answer = _extract_tool_results_and_final_answer(events)

    if final_answer is None:
        return {
            "is_hallucination": False,
            "confidence": "low",
            "reasoning": "No final text answer found in this run to judge.",
            "final_answer": None,
            "tool_results": tool_results,
        }

    prompt = f"""You are auditing an AI agent's output for hallucination.

The agent had access to ONLY these tool results during its run:
{json.dumps(tool_results, indent=2)}

The agent's final answer to the user was:
"{final_answer}"

Judge whether the final answer states any specific fact, number, or claim
that is NOT supported by the tool results above. Minor rephrasing,
unit conversions of numbers that ARE in the tool results, or reasonable
inference from the given data is NOT a hallucination. Stating a fact that
never appeared in any tool result IS a hallucination.

Respond with ONLY valid JSON, no other text, in this exact shape:
{{"is_hallucination": true or false, "confidence": "high" or "medium" or "low", "reasoning": "one or two sentences explaining your verdict"}}
"""

    response = _get_client().messages.create(
        model=JUDGE_MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = "".join(b.text for b in response.content if b.type == "text").strip()

    try:
        verdict = json.loads(raw_text)
    except json.JSONDecodeError:
        # Fail safe: if the judge didn't return clean JSON, don't crash —
        # surface it as an unverifiable result rather than a false positive/negative.
        verdict = {
            "is_hallucination": False,
            "confidence": "low",
            "reasoning": f"Judge response was not valid JSON: {raw_text[:200]}",
        }

    return {
        **verdict,
        "final_answer": final_answer,
        "tool_results": tool_results,
    }


def judge_regression(run_a_events: list[dict], run_b_events: list[dict],
                      run_a_label: str = "A", run_b_label: str = "B") -> dict:
    """
    Compares two runs (e.g. two prompt versions on the same task) and asks
    the judge which performed better, for prompt regression detection.
    """
    _, answer_a = _extract_tool_results_and_final_answer(run_a_events)
    _, answer_b = _extract_tool_results_and_final_answer(run_b_events)

    prompt = f"""Compare two AI agent responses to the same underlying task.

Response {run_a_label}:
"{answer_a}"

Response {run_b_label}:
"{answer_b}"

Judge which response is better: more accurate, more complete, more clearly
written. If they are roughly equivalent in quality, say so explicitly.

Respond with ONLY valid JSON, no other text, in this exact shape:
{{"better": "{run_a_label}" or "{run_b_label}" or "tie", "reasoning": "one or two sentences"}}
"""

    response = _get_client().messages.create(
        model=JUDGE_MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = "".join(b.text for b in response.content if b.type == "text").strip()

    try:
        verdict = json.loads(raw_text)
    except json.JSONDecodeError:
        verdict = {"better": "tie", "reasoning": f"Judge response was not valid JSON: {raw_text[:200]}"}

    return verdict