"""
AgentOps SDK core.

This module gives you two things:
  1. `wrap(client)` — wraps an Anthropic client so every `.messages.create()`
     call is automatically captured as an "llm_call" event.
  2. `@trace_tool` — a decorator you put on your own tool functions so every
     call is captured as a "tool_call" event.

Both write events into a shared in-memory list for the current "run"
(tracked via `start_run()` / `end_run()`). In Milestone 3 we'll replace the
in-memory list with real Postgres writes — nothing about the calling code
will need to change, which is the whole point of separating capture from
storage.
"""

import time
import uuid
import json
import functools
from contextvars import ContextVar
import requests
import os


# Holds the events for the currently active run. ContextVar (not a plain
# global) so this would work correctly even with concurrent/async runs later.
_current_run = ContextVar("current_run", default=None)


class Run:
    """Represents one full agent execution — a container for its events."""

    def __init__(self, name: str):
        self.id = str(uuid.uuid4())
        self.name = name
        self.start_time = time.time()
        self.end_time = None
        self.events = []

    def add_event(self, event: dict):
        self.events.append(event)

    def finish(self):
        self.end_time = time.time()

    def to_dict(self):
        return {
            "run_id": self.id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_sec": (self.end_time or time.time()) - self.start_time,
            "events": self.events,
        }


def start_run(name: str = "agent_run") -> Run:
    """Call this at the start of an agent run. Returns the Run object."""
    run = Run(name)
    _current_run.set(run)
    return run

AGENTOPS_API_URL = os.environ.get("AGENTOPS_API_URL", "http://localhost:8000")


def end_run() -> dict:
    """Call this when the agent run is done. Sends the trace to the AgentOps
    API for storage, and returns it locally too."""
    run = _current_run.get()
    if run is None:
        raise RuntimeError("end_run() called but no run was started")
    run.finish()
    trace = run.to_dict()

    try:
        resp = requests.post(f"{AGENTOPS_API_URL}/traces", json=trace, timeout=5)
        resp.raise_for_status()
        print(f"\n✅ Trace sent to AgentOps API: {AGENTOPS_API_URL}/runs/{run.id}")
    except requests.exceptions.RequestException as e:
        # Fail open: never let observability break the agent itself.
        print(f"\n⚠️  Could not send trace to AgentOps API ({e}). Trace kept in memory only.")

    _current_run.set(None)
    return trace


def _record_event(event_type: str, name: str, input_data, output_data,
                   start_time: float, end_time: float, error: str = None,
                   tokens_in: int = None, tokens_out: int = None):
    run = _current_run.get()
    if run is None:
        # No active run — don't crash the agent just because tracing wasn't
        # started. Real SDKs fail open like this so instrumentation never
        # breaks production code.
        return

    event = {
        "id": str(uuid.uuid4()),
        "run_id": run.id,
        "type": event_type,
        "name": name,
        "input": input_data,
        "output": output_data,
        "start_time": start_time,
        "end_time": end_time,
        "duration_sec": end_time - start_time,
        "error": error,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }
    run.add_event(event)


def trace_tool(func):
    """Decorator: wraps a tool function so every call is captured."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        error = None
        result = None
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            error = str(e)
            raise
        finally:
            end = time.time()
            # capture positional+keyword args together as the "input"
            input_repr = {"args": args, "kwargs": kwargs}
            _record_event(
                event_type="tool_call",
                name=func.__name__,
                input_data=input_repr,
                output_data=result,
                start_time=start,
                end_time=end,
                error=error,
            )
    return wrapper

def _serialize_content(content):
    """
    Anthropic message content can be a plain string, or a list of content
    blocks (TextBlock, ToolUseBlock, etc. -- SDK objects, not plain dicts).
    Convert everything into plain JSON-able dicts so stored traces are
    clean structured data, not stringified Python objects.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        serialized = []
        for block in content:
            if isinstance(block, dict):
                serialized.append(block)  # already plain (e.g. tool_result we built ourselves)
            else:
                serialized.append({
                    "type": getattr(block, "type", None),
                    "text": getattr(block, "text", None),
                    "tool_use_id": getattr(block, "id", None) if getattr(block, "type", None) == "tool_use" else getattr(block, "tool_use_id", None),
                    "name": getattr(block, "name", None),
                    "input": getattr(block, "input", None),
                })
        return serialized
    return content


def _serialize_messages(messages):
    return [
        {"role": m["role"], "content": _serialize_content(m["content"])}
        for m in messages
    ]


class _WrappedMessages:
    """Stands in for client.messages, intercepting .create() calls."""

    def __init__(self, real_messages):
        self._real_messages = real_messages

    def create(self, *args, **kwargs):
        start = time.time()
        error = None
        response = None
        try:
            response = self._real_messages.create(*args, **kwargs)
            return response
        except Exception as e:
            error = str(e)
            raise
        finally:
            end = time.time()
            tokens_in = getattr(response.usage, "input_tokens", None) if response else None
            tokens_out = getattr(response.usage, "output_tokens", None) if response else None

            # Summarize output content for the trace (text + any tool calls)
            output_summary = None
            if response is not None:
                output_summary = [
                    {"type": b.type, "text": getattr(b, "text", None),
                     "tool_name": getattr(b, "name", None),
                     "tool_input": getattr(b, "input", None)}
                    for b in response.content
                ]

            _record_event(
                event_type="llm_call",
                name=kwargs.get("model", "unknown_model"),
                input_data={"messages": _serialize_messages(kwargs.get("messages", []))},
                output_data=output_summary,
                start_time=start,
                end_time=end,
                error=error,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )


def wrap(client):
    """
    Wrap an Anthropic client so every client.messages.create() call is
    automatically captured. This is the AgentOps.wrap(agent) entry point.

    Usage:
        client = Anthropic(api_key=...)
        client = wrap(client)
        # use client exactly as before — tracing happens transparently
    """
    client.messages = _WrappedMessages(client.messages)
    return client