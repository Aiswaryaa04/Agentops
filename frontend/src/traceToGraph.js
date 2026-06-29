const NODE_WIDTH = 220;
const NODE_GAP = 260;

const COLOR_LLM = "#ffb347";   // amber: thinking
const COLOR_TOOL = "#5eead4";  // cyan: action
const COLOR_FLAG = "#ff5f56";  // red: flagged

export function traceToGraph(events, flags) {
  const flagsByEventId = {};
  for (const flag of flags) {
    if (flag.event_id) {
      flagsByEventId[flag.event_id] = flagsByEventId[flag.event_id] || [];
      flagsByEventId[flag.event_id].push(flag);
    }
  }

  const nodes = events.map((event, index) => {
    const eventFlags = flagsByEventId[event.id] || [];
    const hasFlag = eventFlags.length > 0;

    let color = event.type === "tool_call" ? COLOR_TOOL : COLOR_LLM;
    if (hasFlag) color = COLOR_FLAG;

    const label =
      event.type === "llm_call"
        ? `◆ ${event.name}\n${event.tokens_in ?? "?"}in / ${event.tokens_out ?? "?"}out`
        : `▸ ${event.name}`;

    return {
      id: event.id,
      position: { x: index * NODE_GAP, y: event.type === "llm_call" ? 0 : 130 },
      data: { label, event, flags: eventFlags },
      className: hasFlag ? "node-flagged" : "",
      style: {
        background: "#101010",
        color: "#e8e8e3",
        border: `1.5px solid ${color}`,
        borderRadius: 5,
        padding: "10px 12px",
        width: NODE_WIDTH,
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 11.5,
        whiteSpace: "pre-line",
        boxShadow: hasFlag ? `0 0 12px ${color}55` : "none",
      },
    };
  });

  const edges = [];
  for (let i = 0; i < events.length - 1; i++) {
    const targetFlagged = (flagsByEventId[events[i + 1].id] || []).length > 0;
    edges.push({
      id: `e-${events[i].id}-${events[i + 1].id}`,
      source: events[i].id,
      target: events[i + 1].id,
      animated: targetFlagged,
      style: { stroke: targetFlagged ? COLOR_FLAG : "#333", strokeWidth: 1.5 },
    });
  }

  return { nodes, edges };
}