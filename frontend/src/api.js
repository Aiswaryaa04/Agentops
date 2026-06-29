import axios from "axios";

const API_BASE = "http://localhost:8000";

export async function fetchRuns() {
  const res = await axios.get(`${API_BASE}/runs`);
  return res.data;
}

export async function fetchRunDetail(runId) {
  const res = await axios.get(`${API_BASE}/runs/${runId}`);
  return res.data;
}

export async function fetchFlags(runId) {
  const res = await axios.get(`${API_BASE}/runs/${runId}/flags`);
  return res.data;
}

export async function analyzeRun(runId) {
  const res = await axios.post(`${API_BASE}/runs/${runId}/analyze`);
  return res.data;
}