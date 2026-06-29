import { useState } from "react";
import RunList from "./RunList";
import TraceViewer from "./TraceViewer";
import CostDashboard from "./CostDashboard";

export default function App() {
  const [view, setView] = useState({ page: "list" }); // {page:"list"} | {page:"trace", runId} | {page:"cost"}

  if (view.page === "trace") {
    return <TraceViewer runId={view.runId} onBack={() => setView({ page: "list" })} />;
  }
  if (view.page === "cost") {
    return <CostDashboard onBack={() => setView({ page: "list" })} />;
  }

  return (
    <RunList
      onSelectRun={(runId) => setView({ page: "trace", runId })}
      onOpenCostDashboard={() => setView({ page: "cost" })}
    />
  );
}