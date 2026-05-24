// Lightweight API client. All requests go through Next's rewrite proxy to the
// FastAPI backend, so the browser only ever talks to same-origin /api/*.

export interface Repo {
  id: number;
  name: string;
  url: string;
  language: string;
  status: string;
  n_files: number;
  n_chunks: number;
  created_at: string;
}

export interface Step {
  seq: number;
  agent: string;
  status: string;
  message: string;
  latency_ms: number;
}

export interface RunDetail {
  run: {
    id: number;
    repo_id: number;
    user_task: string;
    status: string;
    mode: string;
    total_latency_ms: number;
    total_retries: number;
  };
  plan: Record<string, any>;
  steps: Step[];
  retrieved: Array<Record<string, any>>;
  test_runs: Array<Record<string, any>>;
  diff: string;
  pr_summary: string;
  evaluation: Record<string, any>;
}

export interface DashboardMetrics {
  repos_indexed: number;
  chunks_indexed: number;
  total_runs: number;
  success_rate: number;
  avg_latency_ms: number;
  avg_retries: number;
  avg_score: number;
  avg_precision_at_k: number;
  avg_test_pass_rate: number;
  tool_call_success_rate: number;
  recent_runs: Array<{
    id: number;
    repo_id: number;
    task: string;
    status: string;
    latency_ms: number;
    retries: number;
    started_at: string | null;
  }>;
}

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => fetch("/api/health").then((r) => j<any>(r)),
  metrics: () => fetch("/api/metrics/agent-runs").then((r) => j<DashboardMetrics>(r)),
  listRepos: () => fetch("/api/repos").then((r) => j<Repo[]>(r)),
  getRepo: (id: number) => fetch(`/api/repos/${id}`).then((r) => j<Repo>(r)),
  ingest: (url: string, name?: string) =>
    fetch("/api/repos/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, name }),
    }).then((r) => j<Repo>(r)),
  chat: (repoId: number, query: string) =>
    fetch(`/api/repos/${repoId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    }).then((r) => j<{ answer: string; chunks: any[] }>(r)),
  runAgent: (repoId: number, task: string) =>
    fetch("/api/agents/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_id: repoId, task }),
    }).then((r) => j<RunDetail>(r)),
  getRun: (runId: number) => fetch(`/api/agents/${runId}`).then((r) => j<RunDetail>(r)),
};
