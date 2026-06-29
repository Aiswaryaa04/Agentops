from dotenv import load_dotenv
load_dotenv()

"""
A real LangGraph agent (not our toy loop) using the SAME tools as
toy_agent, instrumented via AgentOpsCallbackHandler instead of wrap().
This proves the SDK works on a framework we don't control internally.
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from agentops_sdk import start_run, end_run, AgentOpsCallbackHandler

# Reuse the exact same knowledge base as toy_agent, redefined here as
# LangChain @tool-decorated functions (LangChain tools need this decorator
# so the agent knows their name/description/schema automatically).
FAKE_KNOWLEDGE_BASE = {
    "speed of light": "299,792,458 meters per second",
    "boiling point of water": "100 degrees Celsius at sea level",
    "population of france": "approximately 68 million (2024 estimate)",
}


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression. e.g. '23 * 4 + 1'"""
    try:
        allowed = "0123456789+-*/(). "
        if not all(c in allowed for c in expression):
            return "Error: expression contains disallowed characters"
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"Error: {e}"


@tool
def search(query: str) -> str:
    """Search a knowledge base for a fact."""
    query_lower = query.lower().strip()
    for key, value in FAKE_KNOWLEDGE_BASE.items():
        if key in query_lower or query_lower in key:
            return value
    return f"No results found for '{query}'"


def run_langgraph_agent(task: str):
    model = ChatAnthropic(model="claude-sonnet-4-6")
    graph = create_react_agent(model, tools=[calculator, search])

    start_run(name="langgraph_speed_of_light_task")

    result = graph.invoke(
        {"messages": [{"role": "user", "content": task}]},
        config={"callbacks": [AgentOpsCallbackHandler()]},
    )

    final_message = result["messages"][-1]
    print(f"\nFinal answer: {final_message.content}")

    end_run()
    return final_message.content


if __name__ == "__main__":
    task = (
        "What is the speed of light, and what is that number divided by 1000? "
        "Give me both the fact and the calculation result."
    )
    run_langgraph_agent(task)