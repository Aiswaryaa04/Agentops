# AgentOps

AgentOps is an observability platform for AI agents. If you have ever built an agent that calls tools in a loop, you have probably run into the same problem: it works fine while you are watching it in a terminal, and then something goes wrong in a longer run and you have no idea what happened. There is no equivalent of a debugger or a log viewer built for this. AgentOps is my attempt at building that tool myself, end to end.

It instruments an agent's execution (every LLM call, every tool call, token counts, timing), stores that as structured trace data, and gives you a UI to look back at any run as a visual graph, replay it step by step, see what it cost, and get automatic flags when something looks wrong, including a flag for hallucination that is judged by Claude itself rather than a simple keyword check.

It works across three different ways of building agents: a hand written agent loop, LangGraph, and CrewAI, using the same backend and the same UI for all three.

## Why I built it this way

The project is split into independent pieces on purpose. The SDK only cares about capturing events. The backend only cares about storing and serving them. The frontend only cares about displaying them. None of these pieces know about the others' internals. That separation is what let me add a third agent framework (CrewAI) near the end of the project without touching the database schema, the API, or a single line of the frontend.

It also meant that when something broke, like a value coming through as null or a graph hiding a node behind a panel, the bug was almost always isolated to one of these layers, which made debugging far less painful than it could have been.

## Architecture

```
Your agent code (custom loop, LangGraph, or CrewAI)
        |
        |  instrumented by the AgentOps SDK
        |  (wrap() for direct client calls, or a framework callback/listener)
        v
Trace events captured in memory during the run
        |
        |  sent as one HTTP POST when the run finishes
        v
FastAPI ingestion API
        |
        v
PostgreSQL  (runs, events, failure_flags tables)
        ^
        |  read by
        |
React frontend (trace graph, replay mode, cost dashboard)
```

The SDK never talks to Postgres directly, and the frontend never talks to Postgres directly either. Everything goes through the API. This is a small constraint but it means the storage layer can change without anything else needing to know.

## What is actually being captured

Every LLM call and every tool call becomes one event, with a type, a name, its input and output, start and end time, and (for LLM calls) token counts. Events are grouped under a run. Tool calls are always free, since they run locally rather than calling out to a paid model.

The schema is intentionally simple: two main tables, runs and events, plus a third table, failure_flags, that any kind of detector (rule based or LLM based) can write into. This is also why cost is calculated on the fly from token counts instead of being stored as a dollar amount directly. Prices change, but a token count never does, so storing the raw number and computing cost at read time means nothing has to be rewritten if Anthropic changes pricing later.

## Failure detection

Three of the four failure types are detected with plain rules running against the stored event data, no model call involved.

An infinite loop is flagged when the same tool gets called with the same input three or more times in one run. A token blowout is flagged when a single LLM call's combined input and output tokens cross a threshold. A tool or retrieval error is flagged when a tool call either raised an error or came back with an explicit "not found" type result.

The fourth type, hallucination, cannot be caught with a rule, because it requires understanding whether a sentence is actually supported by the data the agent had access to. For that one, the platform sends the agent's tool results and its final answer to Claude and asks it to judge whether anything in the final answer is unsupported. The same mechanism is used to compare two runs against each other for prompt regression testing, asking which of two outputs is better and why.

## The frontend

Opening the app shows a list of every run that has been traced. Clicking into one shows the run as a graph, amber for LLM calls and cyan for tool calls, red and pulsing for anything that got flagged. Clicking a node opens a panel with its full input, output, timing, and cost if it is an LLM call.

There is also a replay mode, which steps through the run's events in order with a short delay between each one, dimming everything except the current step, so you can watch a run reconstruct itself rather than just inspecting nodes individually. A separate cost dashboard page aggregates spend across every run rather than just one at a time.

## Supported agent frameworks

A custom agent loop is instrumented with `wrap()` around the Anthropic client and a `@trace_tool` decorator on tool functions. This requires no change to how the loop itself works.

LangGraph is instrumented with a callback handler, since LangGraph manages its own model client internally and there is nothing to wrap directly. You pass `AgentOpsCallbackHandler()` into the run's config.

CrewAI is instrumented with an event listener subscribed to CrewAI's own event bus, since CrewAI also manages its model calls internally and exposes a different mechanism (events rather than callbacks) for hooking into them.

In all three cases the same underlying event format ends up in the same database and renders in the same UI. The actual hook mechanism is the only thing that differs per framework, which was the main thing I wanted to prove by adding a second and third framework rather than stopping at one.

## Known limitations

A few things are true about this project as it stands, worth being upfront about rather than overstating.

There is no concept of separate projects or teams. Every run from every script that points at the same backend lands in the same shared list. Adding real multi tenancy would mean adding a project identifier to the schema and filtering by it, which is a fairly small change but has not been done here.

CrewAI's tool usage events do not currently include the tool's actual return value (this is a gap in CrewAI itself, not something this project failed to capture), so tool call outputs from CrewAI runs will show up as null in the trace even though the timing and input are accurate.

Replay mode is a fixed interval step through, not based on the actual recorded duration of each step, so it does not represent real time passing during the original run, just the order it happened in.

The free hosting tier used for the backend spins down after a period of inactivity, so the very first request after a while will take longer than usual to respond.

## Running it locally

You will need Python, Node, and a local Postgres installation.

Clone the repo, then for the backend:

```
cd backend
pip install -r requirements.txt
psql postgres -c "CREATE DATABASE agentops;"
psql agentops -f schema.sql
uvicorn main:app --reload --port 8000
```

For the frontend, in a separate terminal:

```
cd frontend
npm install
npm run dev
```

Add a `.env` file in the project root with your own key:

```
ANTHROPIC_API_KEY=your-key-here
```

Then run any of the example agents to generate a trace, for instance:

```
cd toy_agent
python agent.py
```

and open the frontend in your browser to see it appear.

## Deployment

The backend, database, and frontend are deployed separately on Render, as a FastAPI web service, a managed Postgres instance, and a static site. The frontend is built with a `VITE_API_BASE` environment variable pointing at the deployed backend URL, since Vite bakes that value into the build at build time rather than reading it at runtime.

To point another project's agent at the deployed version instead of a local one, set `AGENTOPS_API_URL` to the deployed backend's URL and `ANTHROPIC_API_KEY` to your key, then use the SDK exactly as shown above. The deployed frontend will show that project's runs alongside everything else already in the database.