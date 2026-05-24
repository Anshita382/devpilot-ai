"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, DashboardMetrics } from "@/lib/api";
import { Card, StatusPill } from "@/components/ui";

function Stat({
  label,
  value,
  accent,
  suffix = "",
}: {
  label: string;
  value: string | number;
  accent?: string;
  suffix?: string;
}) {
  return (
    <Card className="p-6">
      <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-mist">{label}</div>
      <div className="mt-3 flex items-baseline gap-1">
        <span
          className="font-display text-5xl font-600 tabular-nums"
          style={{ color: accent || "#ede8df" }}
        >
          {value}
        </span>
        {suffix && <span className="font-mono text-sm text-mist">{suffix}</span>}
      </div>
    </Card>
  );
}

export default function DashboardPage() {
  const [m, setM] = useState<DashboardMetrics | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.metrics().then(setM).catch((e) => setErr(String(e)));
  }, []);

  return (
    <div className="space-y-10">
      <header className="rise">
        <div className="font-mono text-xs uppercase tracking-[0.3em] text-ember">
          Operating System
        </div>
        <h1 className="mt-2 font-display text-6xl font-600 italic leading-none tracking-tight">
          The flight deck.
        </h1>
        <p className="mt-4 max-w-xl text-mist">
          A multi-agent engineering pipeline — plan, retrieve, code, test, review, evaluate —
          running locally over your repositories with full telemetry.
        </p>
      </header>

      {err && (
        <Card className="border-ember/40 p-5 text-ember">
          <div className="font-mono text-xs uppercase tracking-widest">Backend unreachable</div>
          <p className="mt-2 text-sm">
            Start the API: <code className="text-bone">cd backend && uvicorn app.main:app</code>
          </p>
        </Card>
      )}

      {m && (
        <>
          <section className="grid grid-cols-2 gap-4 rise md:grid-cols-4">
            <Stat label="Agent Runs" value={m.total_runs} accent="#5ad1ff" />
            <Stat
              label="Success Rate"
              value={Math.round(m.success_rate * 100)}
              suffix="%"
              accent="#c6ff4a"
            />
            <Stat label="Mean Latency" value={m.avg_latency_ms} suffix="ms" />
            <Stat label="Composite Score" value={m.avg_score} accent="#ff5b3a" />
          </section>

          <section className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Stat label="Repos Indexed" value={m.repos_indexed} />
            <Stat label="Chunks Indexed" value={m.chunks_indexed} />
            <Stat
              label="Retrieval P@k"
              value={Math.round(m.avg_precision_at_k * 100)}
              suffix="%"
            />
            <Stat
              label="Tool Success"
              value={Math.round(m.tool_call_success_rate * 100)}
              suffix="%"
            />
          </section>

          <section>
            <div className="mb-4 flex items-end justify-between">
              <h2 className="font-display text-2xl font-500 italic">Recent runs</h2>
              <Link
                href="/repos"
                className="font-mono text-xs uppercase tracking-widest text-azure hover:text-bone"
              >
                Start a run →
              </Link>
            </div>
            <Card className="divide-y divide-ink-800 overflow-hidden">
              {m.recent_runs.length === 0 && (
                <div className="p-8 text-center text-mist">
                  No runs yet. Seed the demo:{" "}
                  <code className="text-bone">python scripts/seed_demo.py</code>
                </div>
              )}
              {m.recent_runs.map((r) => (
                <Link
                  key={r.id}
                  href={`/agents/${r.id}`}
                  className="flex items-center justify-between px-5 py-4 transition-colors hover:bg-ink-850"
                >
                  <div className="flex items-center gap-4">
                    <span className="font-mono text-xs text-mist">#{r.id}</span>
                    <span className="text-bone">{r.task}</span>
                  </div>
                  <div className="flex items-center gap-6">
                    <span className="font-mono text-xs text-mist">{r.latency_ms}ms</span>
                    <span className="font-mono text-xs text-mist">{r.retries} retries</span>
                    <StatusPill status={r.status} />
                  </div>
                </Link>
              ))}
            </Card>
          </section>
        </>
      )}
    </div>
  );
}
