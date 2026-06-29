"""
CrewAI adapter, using CrewAI's event-bus system.

Import path: top-level `crewai.events` (confirmed via crewai.events.__all__
on the installed version -- NOT crewai.utilities.events).

Event correlation: CrewAI's LLMCallCompletedEvent includes a
`started_event_id` field that references the matching LLMCallStartedEvent's
own `event_id` -- this is the correct, built-in way to pair start/end
events, confirmed via LLMCallCompletedEvent.model_fields. (An earlier
version of this file incorrectly used Python's id(event) for correlation,
which doesn't work since CrewAI emits a new event object for each phase.)

Usage dict shape: confirmed directly from CrewAI's source
(LLM._usage_to_dict docstring) -- plain keys 'prompt_tokens',
'completion_tokens', 'total_tokens', untouched from LiteLLM's standard
shape.
"""

import time
from crewai.events import (
    BaseEventListener,
    LLMCallStartedEvent,
    LLMCallCompletedEvent,
    LLMCallFailedEvent,
    ToolUsageStartedEvent,
    ToolUsageFinishedEvent,
    ToolUsageErrorEvent,
)
from .tracer import _record_event


class AgentOpsCrewListener(BaseEventListener):
    """
    Instantiate once, keep the instance alive for the whole run:
        listener = AgentOpsCrewListener()
    """

    def __init__(self):
        super().__init__()
        # Keyed by each event's own event_id, so completed/failed events
        # can look up their matching start via started_event_id.
        self._llm_call_starts = {}
        self._tool_call_starts = {}

    def setup_listeners(self, crewai_event_bus):

        @crewai_event_bus.on(LLMCallStartedEvent)
        def on_llm_call_started(source, event: LLMCallStartedEvent):
            self._llm_call_starts[event.event_id] = {
                "start_time": time.time(),
                "messages": event.messages,
            }
        
        @crewai_event_bus.on(LLMCallCompletedEvent)
        def on_llm_call_completed(source, event: LLMCallCompletedEvent):
            start_info = self._llm_call_starts.pop(event.started_event_id, None)
            start_time = start_info["start_time"] if start_info else time.time()
            end_time = time.time()

            usage = event.usage or {}
            tokens_in = usage.get("input_tokens")
            tokens_out = usage.get("output_tokens")

            _record_event(
                event_type="llm_call",
                name=event.model or "unknown_model",
                input_data={"messages": str(start_info["messages"] if start_info else event.messages)},
                output_data=[{"type": "text", "text": str(event.response)}],
                start_time=start_time,
                end_time=end_time,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )

        @crewai_event_bus.on(LLMCallFailedEvent)
        def on_llm_call_failed(source, event: LLMCallFailedEvent):
            start_info = self._llm_call_starts.pop(getattr(event, "started_event_id", None), None)
            start_time = start_info["start_time"] if start_info else time.time()
            now = time.time()

            _record_event(
                event_type="llm_call",
                name="unknown_model",
                input_data={},
                output_data=None,
                start_time=start_time,
                end_time=now,
                error=str(getattr(event, "error", "unknown error")),
            )

        @crewai_event_bus.on(ToolUsageStartedEvent)
        def on_tool_usage_started(source, event: ToolUsageStartedEvent):
            self._tool_call_starts[event.event_id] = {
                "start_time": time.time(),
                "tool_args": getattr(event, "tool_args", None),
            }

        @crewai_event_bus.on(ToolUsageFinishedEvent)
        def on_tool_usage_finished(source, event: ToolUsageFinishedEvent):
            start_info = self._tool_call_starts.pop(getattr(event, "started_event_id", None), None)

            started_at = getattr(event, "started_at", None)
            finished_at = getattr(event, "finished_at", None)
            start_time = (
                started_at.timestamp() if started_at
                else start_info["start_time"] if start_info
                else time.time()
            )
            end_time = finished_at.timestamp() if finished_at else time.time()

            # NOTE: CrewAI's ToolUsageFinishedEvent does not include the
            # tool's actual return value as of this version (tracked
            # upstream in crewAI issue #2440) -- output stays null. Real
            # CrewAI API gap, not a bug here.
            _record_event(
                event_type="tool_call",
                name=getattr(event, "tool_name", "unknown_tool"),
                input_data={"args": [str(getattr(event, "tool_args", None))], "kwargs": {}},
                output_data=None,
                start_time=start_time,
                end_time=end_time,
            )

        @crewai_event_bus.on(ToolUsageErrorEvent)
        def on_tool_usage_error(source, event: ToolUsageErrorEvent):
            start_info = self._tool_call_starts.pop(getattr(event, "started_event_id", None), None)
            start_time = start_info["start_time"] if start_info else time.time()
            now = time.time()

            _record_event(
                event_type="tool_call",
                name=getattr(event, "tool_name", "unknown_tool"),
                input_data={"args": [str(getattr(event, "tool_args", None))], "kwargs": {}},
                output_data=None,
                start_time=start_time,
                end_time=now,
                error=str(getattr(event, "error", "unknown error")),
            )