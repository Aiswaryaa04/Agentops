import { useState } from "react";
import RunList from "./RunList";
import TraceViewer from "./TraceViewer";

export default function App() {
  const [selectedRunId, setSelectedRunId] = useState(null);

  if (selectedRunId) {
    return <TraceViewer runId={selectedRunId} onBack={() => setSelectedRunId(null)} />;
  }

  return <RunList onSelectRun={setSelectedRunId} />;
}