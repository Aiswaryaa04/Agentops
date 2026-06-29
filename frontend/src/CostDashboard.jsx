import { useEffect, useState } from "react";
import { fetchCostSummary } from "./api";

const COLORS = {
  bg: "#0a0a0a", panel: "#101010", border: "#1f1f1f",
  text: "#e8e8e3", dim: "#6b6b65", amber: "#ffb347", cyan: "#5eead4",
};

function formatCost(usd) {
  if (usd === 0) return "$0";
  if (usd < 0.01) return `$${usd.toFixed(6)}`;
  return `$${usd.toFixed(4)}`;
}

export default function CostDashboard({ onBack }) {
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    fetchCostSummary().then(setSummary);
  }, []);

  if (!summary) return <div style={styles.loading}>loading cost summary…</div>;

  const maxCost = Math.max(...summary.runs.map((r) => r.cost_usd), 0.000001);

  return (
    <div style={styles.container}>
      <button onClick={onBack} style={styles.backButton}>← runs</button>

      <div style={styles.totalsRow}>
        <div style={styles.totalCard}>
          <div style={styles.totalLabel}>total spend</div>
          <div style={styles.totalValueAmber}>{formatCost(summary.total_cost_usd)}</div>
        </div>
        <div style={styles.totalCard}>
          <div style={styles.totalLabel}>total input tokens</div>
          <div style={styles.totalValue}>{summary.total_tokens_in.toLocaleString()}</div>
        </div>
        <div style={styles.totalCard}>
          <div style={styles.totalLabel}>total output tokens</div>
          <div style={styles.totalValue}>{summary.total_tokens_out.toLocaleString()}</div>
        </div>
      </div>

      <div style={styles.tableHeader}>cost per run</div>
      <div style={styles.list}>
        {summary.runs.map((run) => (
          <div key={run.run_id} style={styles.row}>
            <div style={styles.rowTop}>
              <span style={styles.runName}>{run.run_name}</span>
              <span style={styles.runCost}>{formatCost(run.cost_usd)}</span>
            </div>
            <div style={styles.barTrack}>
              <div
                style={{
                  ...styles.barFill,
                  width: `${Math.max((run.cost_usd / maxCost) * 100, run.cost_usd > 0 ? 2 : 0)}%`,
                }}
              />
            </div>
            <div style={styles.rowMeta}>
              {run.tokens_in.toLocaleString()}in / {run.tokens_out.toLocaleString()}out
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const styles = {
  container: { background: COLORS.bg, minHeight: "100vh", padding: "40px 60px", color: COLORS.text },
  backButton: {
    background: "none", border: `1px solid ${COLORS.border}`, color: COLORS.dim,
    padding: "6px 14px", borderRadius: 4, cursor: "pointer", fontSize: 12, marginBottom: 30,
  },
  loading: { background: COLORS.bg, color: COLORS.dim, padding: 40, minHeight: "100vh" },
  totalsRow: { display: "flex", gap: 16, marginBottom: 40 },
  totalCard: {
    flex: 1, background: COLORS.panel, border: `1px solid ${COLORS.border}`,
    borderRadius: 6, padding: "18px 20px",
  },
  totalLabel: { fontSize: 11, color: COLORS.dim, marginBottom: 8 },
  totalValueAmber: { fontSize: 22, color: COLORS.amber, fontWeight: 500 },
  totalValue: { fontSize: 22, color: COLORS.text, fontWeight: 500 },
  tableHeader: { fontSize: 11, color: COLORS.dim, letterSpacing: 1, marginBottom: 12 },
  list: { display: "flex", flexDirection: "column", gap: 14 },
  row: {
    background: COLORS.panel, border: `1px solid ${COLORS.border}`,
    borderRadius: 6, padding: "12px 16px",
  },
  rowTop: { display: "flex", justifyContent: "space-between", marginBottom: 8, fontSize: 13 },
  runName: { color: COLORS.text },
  runCost: { color: COLORS.amber },
  barTrack: { height: 5, background: "#1a1a1a", borderRadius: 3, overflow: "hidden" },
  barFill: { height: "100%", background: COLORS.cyan, borderRadius: 3 },
  rowMeta: { fontSize: 10, color: COLORS.dim, marginTop: 6 },
};