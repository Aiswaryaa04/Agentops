from dotenv import load_dotenv
load_dotenv()

"""
AgentOps ingestion API.

The SDK POSTs completed traces here; the (future) frontend GETs them from
here. This is the only thing that talks to Postgres directly — neither the
SDK nor the frontend ever connects to the database itself, which keeps the
schema free to change without breaking other parts of the system.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Any
import db
import failure_detection  
import cost
import llm_judge

app = FastAPI(title="AgentOps Ingestion API")

# Allow the frontend (running on a different port) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://agentops-1-flxi.onrender.com"],  
    allow_methods=["*"],
    allow_headers=["*"],
)


class EventIn(BaseModel):
    id: str
    run_id: str
    type: str
    name: str
    input: Optional[Any] = None
    output: Optional[Any] = None
    start_time: float
    end_time: float
    duration_sec: float
    error: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None


class TraceIn(BaseModel):
    run_id: str
    name: str
    start_time: float
    end_time: float
    events: list[EventIn]


@app.post("/traces")
def ingest_trace(trace: TraceIn):
    """Receives one completed run + all its events, writes them to Postgres."""
    db.insert_run(
        run_id=trace.run_id,
        name=trace.name,
        start_time=trace.start_time,
        end_time=trace.end_time,
        status="completed",
    )
    db.insert_events([e.dict() for e in trace.events])
    return {"status": "ok", "run_id": trace.run_id, "events_stored": len(trace.events)}


@app.get("/runs")
def list_runs():
    return db.fetch_runs()


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    run = db.fetch_run_with_events(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run

@app.get("/runs/{run_id}/flags")
def get_flags(run_id: str):
    return db.fetch_flags(run_id)

@app.post("/runs/{run_id}/analyze")
def analyze_run(run_id: str):
    """Runs failure detection on a stored run and persists any flags found."""
    run = db.fetch_run_with_events(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    db.delete_flags_for_run(run_id)  

    flags = failure_detection.run_all_detectors(run["events"])
    db.insert_flags(run_id, flags)

    return {"run_id": run_id, "flags_found": len(flags), "flags": flags}

@app.get("/runs/{run_id}/cost")
def get_run_cost(run_id: str):
    run = db.fetch_run_with_events(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return cost.run_cost_breakdown(run["events"])

@app.post("/runs/{run_id}/judge_hallucination")
def judge_run_hallucination(run_id: str):
    run = db.fetch_run_with_events(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    verdict = llm_judge.judge_hallucination(run["events"])

    # Persist as a failure flag if hallucination was found, same table as the
    # rule-based detectors -- keeps all flags queryable in one place.
    if verdict["is_hallucination"]:
        import uuid
        db.insert_flags(run_id, [{
            "id": str(uuid.uuid4()),
            "event_id": None,  # run-level judgment, not tied to one event
            "flag_type": "hallucination",
            "severity": "critical",
            "description": verdict["reasoning"],
        }])

    return verdict


@app.post("/runs/compare")
def compare_runs(run_a_id: str, run_b_id: str):
    run_a = db.fetch_run_with_events(run_a_id)
    run_b = db.fetch_run_with_events(run_b_id)
    if run_a is None or run_b is None:
        raise HTTPException(status_code=404, detail="One or both runs not found")

    return llm_judge.judge_regression(
        run_a["events"], run_b["events"],
        run_a_label=run_a["name"], run_b_label=run_b["name"],
    )

@app.get("/cost-summary")
def get_cost_summary():
    runs = db.fetch_runs()
    runs_with_events = [db.fetch_run_with_events(r["id"]) for r in runs]
    return cost.all_runs_cost_summary(runs_with_events)