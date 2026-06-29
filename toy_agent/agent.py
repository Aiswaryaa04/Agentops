"""
The toy agent.

Uses Anthropic's real tool-use API (not text-parsing hacks) — the same
mechanism LangGraph/CrewAI use under the hood. Claude's response either
contains a `tool_use` block (it wants to call a tool) or a final text
answer. We run the tool, send the result back as a `tool_result`, and loop.
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from anthropic import Anthropic
from tools import TOOLS
from agentops_sdk import wrap, start_run, end_run

MODEL = "claude-sonnet-4-6"
MAX_STEPS = 8  # safety cap so a broken loop can't run forever


def build_tool_schemas():
    """Convert our TOOLS registry into the JSON schema Claude's API expects."""
    schemas = []
    for name, spec in TOOLS.items():
        schemas.append({
            "name": name,
            "description": spec["description"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "The input to the tool"}
                },
                "required": ["input"],
            },
        })
    return schemas


def run_agent(task: str):
    """
    Run the agent loop on a task. Returns the final text answer.
    Prints each step so you can see the loop happening in real time.
    """
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    client = wrap(client)  # <-- this is the entire instrumentation step
    tool_schemas = build_tool_schemas()

    messages = [{"role": "user", "content": task}]

    for step in range(MAX_STEPS):
        print(f"\n--- Step {step + 1} ---")

        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=tool_schemas,
            messages=messages,
        )

        # Did Claude ask to use a tool, or give a final answer?
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        if not tool_use_blocks:
            # No tool call -> final answer. Extract the text and stop.
            final_text = "".join(b.text for b in response.content if b.type == "text")
            print(f"Final answer: {final_text}")
            return final_text

        # Append assistant's tool-use message to history
        messages.append({"role": "assistant", "content": response.content})

        # Run every requested tool call and collect results
        tool_results = []
        for block in tool_use_blocks:
            tool_name = block.name
            tool_input = block.input.get("input", "")
            print(f"Agent calls tool: {tool_name}({tool_input!r})")

            if tool_name not in TOOLS:
                output = f"Error: unknown tool '{tool_name}'"
            else:
                output = TOOLS[tool_name]["function"](tool_input)

            print(f"Tool result: {output}")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output,
            })

        # Feed results back to the model and loop again
        messages.append({"role": "user", "content": tool_results})

    print("Stopped: hit MAX_STEPS without a final answer.")
    return None


if __name__ == "__main__":
    start_run(name="speed_of_light_task")
    task = (
        "What is the speed of light, and what is that number divided by 1000? "
        "Give me both the fact and the calculation result."
    )
    run_agent(task)
    end_run()