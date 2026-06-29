import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from crewai import Agent, Task, Crew
from crewai.tools import tool

from agentops_sdk import start_run, end_run, AgentOpsCrewListener

# Instance must stay alive for the whole run -- created at module level.
listener = AgentOpsCrewListener()


@tool("calculator")
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression."""
    try:
        allowed = "0123456789+-*/(). "
        if not all(c in allowed for c in expression):
            return "Error: disallowed characters"
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"Error: {e}"


def run_crewai_agent():
    start_run(name="crewai_speed_of_light_task")

    researcher = Agent(
        role="Physics Researcher",
        goal="Answer physics questions accurately using available tools",
        backstory="An expert who always shows their calculation work.",
        tools=[calculator],
        llm="anthropic/claude-sonnet-4-6",
    )

    task = Task(
        description=(
            "The speed of light is 299792458 meters per second. "
            "Calculate that number divided by 1000 using your calculator tool, "
            "then state both numbers clearly."
        ),
        expected_output="The speed of light and the divided result, both stated clearly.",
        agent=researcher,
    )

    crew = Crew(agents=[researcher], tasks=[task])
    result = crew.kickoff()

    print(f"\nFinal answer: {result}")
    end_run()
    return result


if __name__ == "__main__":
    run_crewai_agent()