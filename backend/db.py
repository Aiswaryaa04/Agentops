"""
Database connection layer. Plain psycopg2, no ORM — at this scale a raw
connection + parameterized queries is simpler to reason about than an ORM,
and you'll actually see the SQL you're running (useful for learning).
"""

import os
import psycopg2
import psycopg2.extras

# Reads from env var if set, otherwise assumes local default Postgres setup.
DATABASE_URL = os.environ.get(
    "AGENTOPS_DATABASE_URL",
    "postgresql://localhost/agentops"
)


def get_connection():
    """Open a new connection. Caller is responsible for closing it."""
    return psycopg2.connect(DATABASE_URL)


def insert_run(run_id: str, name: str, start_time: float, end_time: float, status: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO runs (id, name, start_time, end_time, status)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    end_time = EXCLUDED.end_time,
                    status = EXCLUDED.status
                """,
                (run_id, name, start_time, end_time, status),
            )
        conn.commit()
    finally:
        conn.close()


def insert_events(events: list[dict]):
    if not events:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(
                cur,
                """
                INSERT INTO events (
                    id, run_id, type, name, input, output,
                    start_time, end_time, duration_sec, error,
                    tokens_in, tokens_out
                ) VALUES (
                    %(id)s, %(run_id)s, %(type)s, %(name)s,
                    %(input)s, %(output)s,
                    %(start_time)s, %(end_time)s, %(duration_sec)s, %(error)s,
                    %(tokens_in)s, %(tokens_out)s
                )
                ON CONFLICT (id) DO NOTHING
                """,
                [
                    {**e, "input": psycopg2.extras.Json(e["input"]),
                     "output": psycopg2.extras.Json(e["output"])}
                    for e in events
                ],
            )
        conn.commit()
    finally:
        conn.close()


def fetch_runs():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM runs ORDER BY start_time DESC")
            return cur.fetchall()
    finally:
        conn.close()


def fetch_run_with_events(run_id: str):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM runs WHERE id = %s", (run_id,))
            run = cur.fetchone()
            if run is None:
                return None
            cur.execute(
                "SELECT * FROM events WHERE run_id = %s ORDER BY start_time ASC",
                (run_id,),
            )
            events = cur.fetchall()
            run = dict(run)
            run["events"] = events
            return run
    finally:
        conn.close()

def insert_flags(run_id: str, flags: list[dict]):
    if not flags:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(
                cur,
                """
                INSERT INTO failure_flags (id, run_id, event_id, flag_type, severity, description)
                VALUES (%(id)s, %(run_id)s, %(event_id)s, %(flag_type)s, %(severity)s, %(description)s)
                ON CONFLICT (id) DO NOTHING
                """,
                [{**f, "run_id": run_id} for f in flags],
            )
        conn.commit()
    finally:
        conn.close()


def fetch_flags(run_id: str):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM failure_flags WHERE run_id = %s", (run_id,))
            return cur.fetchall()
    finally:
        conn.close()

def delete_flags_for_run(run_id: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM failure_flags WHERE run_id = %s", (run_id,))
        conn.commit()
    finally:
        conn.close()