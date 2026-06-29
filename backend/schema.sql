CREATE TABLE IF NOT EXISTS runs (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    start_time DOUBLE PRECISION NOT NULL,
    end_time DOUBLE PRECISION,
    status TEXT NOT NULL DEFAULT 'running'  -- running | completed | failed
);

CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    type TEXT NOT NULL,            -- 'llm_call' | 'tool_call'
    name TEXT NOT NULL,
    input JSONB,
    output JSONB,
    start_time DOUBLE PRECISION NOT NULL,
    end_time DOUBLE PRECISION NOT NULL,
    duration_sec DOUBLE PRECISION NOT NULL,
    error TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER
);

CREATE INDEX IF NOT EXISTS idx_events_run_id ON events(run_id);