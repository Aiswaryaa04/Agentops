"""
Real tools the agent can call.

The 'search' tool below stands in for a real web search API — it looks up
real facts from a small dataset deterministically. It's swapping the data
source, not faking the agent's behavior.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from agentops_sdk import trace_tool

FAKE_KNOWLEDGE_BASE = {
    "speed of light": "299,792,458 meters per second",
    "boiling point of water": "100 degrees Celsius at sea level",
    "population of france": "approximately 68 million (2024 estimate)",
}


@trace_tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression. e.g. '23 * 4 + 1'"""
    try:
        allowed = "0123456789+-*/(). "
        if not all(c in allowed for c in expression):
            return "Error: expression contains disallowed characters"
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {e}"


@trace_tool
def search(query: str) -> str:
    """Look up a fact from the knowledge base."""
    query_lower = query.lower().strip()
    for key, value in FAKE_KNOWLEDGE_BASE.items():
        if key in query_lower or query_lower in key:
            return value
    return f"No results found for '{query}'"


TOOLS = {
    "calculator": {
        "function": calculator,
        "description": "Evaluate an arithmetic expression. Input: a math expression string.",
    },
    "search": {
        "function": search,
        "description": "Search a knowledge base for a fact. Input: a search query string.",
    },
}