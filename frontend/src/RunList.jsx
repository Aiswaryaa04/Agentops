import { useEffect, useState } from "react";
import { fetchRuns } from "./api";

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

export default function RunList({ onSelectRun, onOpenCostDashboard }) {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRuns().then((data) => {
      setRuns(data);
      setLoading(false);
    });
  }, []);

  return (
    <div style={styles.container}>
      <div style={styles.prompt}>
        agentops <span style={styles.promptDim}>$</span> runs
        <span className="cursor-blink" style={styles.cursor}>▋</span>
      </div>

      <button onClick={onOpenCostDashboard} style={styles.costDashboardButton}>
        view cost dashboard →
      </button>

      <div style={styles.headerRow}>
        <span style={{ width: 10 }} />
        <span>RUN</span>
        <span style={styles.headerRight}>STATUS</span>
        <span style={styles.headerRight}>ID</span>
      </div>

      {loading && <div style={styles.empty}>loading…</div>}

      {!loading && runs.length === 0 && (
        <div style={styles.empty}>
          no runs yet — execute an agent with AgentOps.wrap() to see traces here
        </div>
      )}

      <div style={styles.list}>
        {runs.map((run) => (
          <div
            key={run.id}
            style={styles.row}
            onClick={() => onSelectRun(run.id)}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#161616")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "#101010")}
          >
            <span style={styles.statusDot(run.status)} />
            <span style={styles.runName}>{run.name}</span>
            <span style={styles.runStatusText(run.status)}>{run.status}</span>
            <span style={styles.runId}>{run.id.slice(0, 8)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

const styles = {
  container: {
    background: COLORS.bg,
    minHeight: "100vh",
    padding: "48px 64px",
    color: COLORS.text,
  },
  prompt: {
    fontSize: 18,
    color: COLORS.amber,
    marginBottom: 20,
    fontWeight: 500,
    letterSpacing: 0.5,
  },
  promptDim: { color: COLORS.dim },
  cursor: { color: COLORS.amber, marginLeft: 4 },
  costDashboardButton: {
    background: "transparent",
    border: `1px solid ${COLORS.amber}`,
    color: COLORS.amber,
    padding: "6px 16px",
    borderRadius: 4,
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 12,
    marginBottom: 28,
    display: "inline-block",
  },
  headerRow: {
    display: "grid",
    gridTemplateColumns: "10px 1fr 100px 100px",
    gap: 16,
    padding: "0 16px 10px",
    fontSize: 11,
    letterSpacing: 1,
    color: COLORS.dim,
    borderBottom: `1px solid ${COLORS.border}`,
    marginBottom: 8,
  },
  headerRight: { justifySelf: "end" },
  list: { display: "flex", flexDirection: "column", gap: 6 },
  empty: { color: COLORS.dim, padding: "20px 16px", fontSize: 13 },
  row: {
    display: "grid",
    gridTemplateColumns: "10px 1fr 100px 100px",
    alignItems: "center",
    gap: 16,
    padding: "14px 16px",
    background: COLORS.panel,
    border: `1px solid ${COLORS.border}`,
    borderRadius: 4,
    cursor: "pointer",
    transition: "background 0.15s ease",
  },
  statusDot: (status) => ({
    width: 7,
    height: 7,
    borderRadius: "50%",
    background: status === "completed" ? COLORS.cyan : COLORS.amber,
    boxShadow: `0 0 6px ${status === "completed" ? COLORS.cyan : COLORS.amber}`,
  }),
  runName: { fontSize: 13, color: COLORS.text },
  runStatusText: (status) => ({
    fontSize: 11,
    justifySelf: "end",
    color: status === "completed" ? COLORS.cyan : COLORS.amber,
  }),
  runId: { fontSize: 11, color: COLORS.dim, justifySelf: "end" },
};