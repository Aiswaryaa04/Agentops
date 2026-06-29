"""
LangGraph/LangChain adapter.

Unlike wrap() (which patches the Anthropic client directly for our toy
agent), LangChain/LangGraph manage their own internal model clients --
we never see them. Instead, LangChain provides a callback system: hooks
that fire automatically on llm_start/end, tool_start/end, regardless of
which framework or model is used underneath.

This proves the SDK's actual product value: the SAME Run/_record_event
core from tracer.py works whether instrumentation comes from wrapping a
client directly (toy_agent) or from framework callbacks (LangGraph) --
only the hook mechanism differs per framework.
"""

import time
import uuid
from langchain_core.callbacks import BaseCallbackHandler
from .tracer import _record_event


class AgentOpsCallbackHandler(BaseCallbackHandler):
    """Pass this to any LangChain/LangGraph agent's `config={"callbacks": [...]}`
    or `.invoke(..., config={"callbacks": [AgentOpsCallbackHandler()]})` to
    automatically capture every LLM call and tool call into the current
    AgentOps run (started separately via start_run() / end_run())."""

    def __init__(self):
        super().__init__()
        self._llm_starts = {}   # run_id (LangChain's) -> start_time, input
        self._tool_starts = {}  # run_id (LangChain's) -> start_time, input

    # --- LLM call hooks ---

    def on_llm_start(self, serialized, prompts, *, run_id, **kwargs):
        self._llm_starts[run_id] = {"start_time": time.time(), "prompts": prompts}

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        # Chat models (like ChatAnthropic) fire this instead of on_llm_start.
        self._llm_starts[run_id] = {"start_time": time.time(), "messages": messages}

    def on_llm_end(self, response, *, run_id, **kwargs):
        start_info = self._llm_starts.pop(run_id, None)
        if start_info is None:
            return

        start_time = start_info["start_time"]
        end_time = time.time()

        tokens_in = tokens_out = None
        model_name = "unknown_model"
        try:
            generation_info = response.generations[0][0]
            message = getattr(generation_info, "message", None)
            response_metadata = getattr(message, "response_metadata", {}) or {}
            model_name = response_metadata.get("model_name", model_name)

            usage = response_metadata.get("usage", {})
            tokens_in = usage.get("input_tokens")
            tokens_out = usage.get("output_tokens")
        except Exception:
            pass

        output_text = None
        try:
            output_text = response.generations[0][0].text
        except Exception:
            pass

        _record_event(
            event_type="llm_call",
            name=model_name,
            input_data={"messages": str(start_info.get("messages") or start_info.get("prompts"))},
            output_data=[{"type": "text", "text": output_text}],
            start_time=start_time,
            end_time=end_time,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )

    # --- Tool call hooks ---

    def on_tool_start(self, serialized, input_str, *, run_id, **kwargs):
        self._tool_starts[run_id] = {
            "start_time": time.time(),
            "tool_name": serialized.get("name", "unknown_tool"),
            "input_str": input_str,
        }

    def on_tool_end(self, output, *, run_id, **kwargs):
        start_info = self._tool_starts.pop(run_id, None)
        if start_info is None:
            return

        _record_event(
            event_type="tool_call",
            name=start_info["tool_name"],
            input_data={"args": [start_info["input_str"]], "kwargs": {}},
            output_data=str(output),
            start_time=start_info["start_time"],
            end_time=time.time(),
        )

    def on_tool_error(self, error, *, run_id, **kwargs):
        start_info = self._tool_starts.pop(run_id, None)
        if start_info is None:
            return

        _record_event(
            event_type="tool_call",
            name=start_info["tool_name"],
            input_data={"args": [start_info["input_str"]], "kwargs": {}},
            output_data=None,
            start_time=start_info["start_time"],
            end_time=time.time(),
            error=str(error),
        )