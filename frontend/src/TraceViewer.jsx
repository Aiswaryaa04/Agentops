import { useEffect, useState } from "react";
import ReactFlow, { Background, Controls, ReactFlowProvider, useReactFlow } from "reactflow";
import "reactflow/dist/style.css";
import { fetchRunDetail, fetchFlags, analyzeRun, fetchRunCost } from "./api";
import { traceToGraph } from "./traceToGraph";

const COLORS = {
  bg: "#0a0a0a",
  panel: "#101010",
  border: "#1f1f1f",
  text: "#e8e8e3",
  dim: "#6b6b65",
  amber: "#ffb347",
  cyan: "#5eead4",
  red: "#ff5f56",
};

function GraphCanvas({ nodes, edges, onNodeClick, panelOpen }) {
  const { fitView } = useReactFlow();

  useEffect(() => {
    const timeout = setTimeout(() => {
      fitView({ padding: 0.2, duration: 200 });
    }, 50);
    return () => clearTimeout(timeout);
  }, [panelOpen, fitView]);

  return (
    <ReactFlow nodes={nodes} edges={edges} onNodeClick={onNodeClick} fitView>
      <Background color="#1a1a1a" gap={22} />
      <Controls style={{ filter: "invert(0.85)" }} />
    </ReactFlow>
  );
}

function formatCost(usd) {
  if (usd === 0) return "$0";
  if (usd < 0.01) return `$${usd.toFixed(6)}`;
  return `$${usd.toFixed(4)}`;
}

export default function TraceViewer({ runId, onBack }) {
  const [run, setRun] = useState(null);
  const [flags, setFlags] = useState([]);
  const [cost, setCost] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [loading, setLoading] = useState(true);

  async function loadData() {
    setLoading(true);
    const runData = await fetchRunDetail(runId);
    const flagData = await fetchFlags(runId);
    const costData = await fetchRunCost(runId);
    setRun(runData);
    setFlags(flagData);
    setCost(costData);
    setLoading(false);
  }

  useEffect(() => {
    loadData();
  }, [runId]);

  async function handleAnalyze() {
    await analyzeRun(runId);
    await loadData();
  }

  if (loading) return <div style={styles.loading}>loading trace…</div>;

  const { nodes, edges } = traceToGraph(run.events, flags);
  const flagCount = flags.length;

  // Look up this event's individual cost from the cost breakdown, by id.
  const costByEventId = {};
  if (cost) {
    for (const e of cost.events) costByEventId[e.event_id] = e.cost_usd;
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <button onClick={onBack} style={styles.backButton}>← runs</button>
        <div style={styles.titleBlock}>
          <span style={styles.runName}>{run.name}</span>
          <span style={styles.runMeta}>
            {run.events.length} events ·{" "}
            <span style={{ color: flagCount > 0 ? COLORS.red : COLORS.dim }}>
              {flagCount} flag{flagCount !== 1 ? "s" : ""}
            </span>
            {cost && (
              <>
                {" · "}
                <span style={{ color: COLORS.amber }}>
                  {formatCost(cost.total_cost_usd)}
                </span>
                {" "}
                <span style={{ color: COLORS.dim }}>
                  ({cost.total_tokens_in}in/{cost.total_tokens_out}out)
                </span>
              </>
            )}
          </span>
        </div>
        <button onClick={handleAnalyze} style={styles.analyzeButton}>re-analyze</button>
      </div>

      <div style={styles.bodyRow}>
        <div style={styles.graphArea}>
          <ReactFlowProvider>
            <GraphCanvas
              nodes={nodes}
              edges={edges}
              onNodeClick={(_, node) => setSelectedEvent(node.data.event)}
              panelOpen={!!selectedEvent}
            />
          </ReactFlowProvider>
        </div>

        {selectedEvent && (
          <div style={styles.detailPanel}>
            <div style={styles.detailHeader}>
              <span>
                <span style={{ color: selectedEvent.type === "llm_call" ? COLORS.amber : COLORS.cyan }}>
                  {selectedEvent.type}
                </span>{" "}
                — {selectedEvent.name}
              </span>
              <button onClick={() => setSelectedEvent(null)} style={styles.closeButton}>✕</button>
            </div>

            {selectedEvent.type === "llm_call" && (
              <div style={styles.costBadge}>
                cost: <span style={{ color: COLORS.amber }}>
                  {formatCost(costByEventId[selectedEvent.id] ?? 0)}
                </span>
              </div>
            )}

            <pre style={styles.detailBody}>{JSON.stringify(selectedEvent, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  );
}

const styles = {
  container: { display: "flex", flexDirection: "column", height: "100vh", background: COLORS.bg },
  header: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "14px 24px", borderBottom: `1px solid ${COLORS.border}`, color: COLORS.text,
  },
  backButton: {
    background: "none", border: `1px solid ${COLORS.border}`, color: COLORS.dim,
    padding: "6px 14px", borderRadius: 4, cursor: "pointer", fontFamily: "inherit", fontSize: 12,
  },
  analyzeButton: {
    background: "transparent", border: `1px solid ${COLORS.amber}`, color: COLORS.amber,
    padding: "6px 16px", borderRadius: 4, cursor: "pointer", fontFamily: "inherit", fontSize: 12,
  },
  titleBlock: { display: "flex", flexDirection: "column", alignItems: "center" },
  runName: { fontSize: 13, fontWeight: 500 },
  runMeta: { fontSize: 11, color: COLORS.dim, marginTop: 2 },
  bodyRow: { flex: 1, display: "flex", minHeight: 0 },
  graphArea: { flex: 1, minWidth: 0 },
  loading: { color: COLORS.dim, padding: 40, fontSize: 13 },
  detailPanel: {
    width: 400, flexShrink: 0,
    background: COLORS.panel, borderLeft: `1px solid ${COLORS.border}`, color: COLORS.text,
    display: "flex", flexDirection: "column",
  },
  detailHeader: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    padding: "12px 18px", borderBottom: `1px solid ${COLORS.border}`, fontSize: 12,
  },
  closeButton: { background: "none", border: "none", color: COLORS.dim, cursor: "pointer", fontSize: 15 },
  costBadge: {
    padding: "10px 18px", fontSize: 12, borderBottom: `1px solid ${COLORS.border}`,
    color: COLORS.dim,
  },
  detailBody: { padding: 18, fontSize: 11, lineHeight: 1.6, overflow: "auto", flex: 1, margin: 0, color: "#b8b8b3" },
};