"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, RunDetail } from "@/lib/api";
import { Card, StatusPill, agentColor } from "@/components/ui";

const PIPELINE = ["planner", "retrieval", "coder", "tester", "reviewer", "evaluator"];

function WorkflowGraph({ steps }: { steps: RunDetail["steps"] }) {
  const seen = new Set(steps.map((s) => s.agent));
  const failed = new Set(steps.filter((s) => s.status === "fail").map((s) => s.agent));
  return (
    <div className="flex items-center justify-between overflow-x-auto py-2">
      {PIPELINE.map((agent, i) => {
        const active = seen.has(agent);
        const color = agentColor(agent);
        return (
          <div key={agent} className="flex items-center">
            <div className="flex flex-col items-center gap-2">
              <div
                className="flex h-14 w-14 items-center justify-center rounded-full border-2 font-mono text-[10px] uppercase tracking-wider transition-all"
                style={{
                  borderColor: active ? color : "rgba(237,232,223,0.15)",
                  background: active ? `${color}1a` : "transparent",
                  color: active ? color : "#9aa0b4",
                  boxShadow: active ? `0 0 24px ${color}33` : "none",
                }}
              >
                {agent.slice(0, 4)}
              </div>
              <span
                className="font-mono text-[9px] uppercase tracking-widest"
                style={{ color: active ? color : "#9aa0b4" }}
              >
                {agent}
                {failed.has(agent) && " ⟳"}
              </span>
            </div>
            {i < PIPELINE.length - 1 && (
              <div
                className="mx-1 h-px w-8 md:w-14"
                style={{ background: active ? `${color}66` : "rgba(237,232,223,0.12)" }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function EvalBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className="flex justify-between font-mono text-[10px] uppercase tracking-widest text-mist">
        <span>{label}</span>
        <span style={{ color }}>{Math.round(value * 100)}%</span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink-800">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${value * 100}%`, background: color }}
        />
      </div>
    </div>
  );
}

function DiffView({ diff }: { diff: string }) {
  const lines = diff.split("\n");
  return (
    <pre className="max-h-[480px] overflow-auto rounded-lg bg-ink-950 p-4 font-mono text-xs leading-relaxed">
      {lines.map((line, i) => {
        let color = "#9aa0b4";
        if (line.startsWith("+") && !line.startsWith("+++")) color = "#c6ff4a";
        else if (line.startsWith("-") && !line.startsWith("---")) color = "#ff5b3a";
        else if (line.startsWith("@@")) color = "#5ad1ff";
        else if (line.startsWith("diff") || line.startsWith("index")) color = "#b78bff";
        return (
          <div key={i} style={{ color }}>
            {line || " "}
          </div>
        );
      })}
    </pre>
  );
}

export default function RunDetailPage() {
  const params = useParams();
  const id = Number(params.runId);
  const [d, setD] = useState<RunDetail | null>(null);
  const [tab, setTab] = useState<"diff" | "summary" | "context">("diff");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.getRun(id).then(setD).catch((e) => setErr(String(e)));
  }, [id]);

  if (err) return <p className="font-mono text-xs text-ember">{err}</p>;
  if (!d) return <div className="text-mist">Loading run…</div>;

  const ev = d.evaluation || {};

  return (
    <div className="space-y-8">
      <header className="rise flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="font-mono text-xs uppercase tracking-[0.3em] text-ember">
            Run #{d.run.id} · {d.run.mode}
          </div>
          <h1 className="mt-2 max-w-2xl font-display text-4xl font-600 italic leading-tight tracking-tight">
            {d.run.user_task}
          </h1>
        </div>
        <div className="flex items-center gap-6">
          <div className="text-right">
            <div className="font-display text-3xl font-600 text-bone tabular-nums">
              {d.run.total_latency_ms}
              <span className="font-mono text-sm text-mist">ms</span>
            </div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-mist">
              {d.run.total_retries} repair iterations
            </div>
          </div>
          <StatusPill status={d.run.status} />
        </div>
      </header>

      <Card className="p-6">
        <WorkflowGraph steps={d.steps} />
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Step timeline */}
        <Card className="p-6 lg:col-span-1">
          <h2 className="font-display text-xl font-500 italic">Timeline</h2>
          <div className="mt-4 space-y-3">
            {d.steps.map((s) => (
              <div key={s.seq} className="flex gap-3">
                <div
                  className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ background: agentColor(s.agent) }}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between">
                    <span
                      className="font-mono text-[10px] uppercase tracking-widest"
                      style={{ color: agentColor(s.agent) }}
                    >
                      {s.agent}
                    </span>
                    <span className="font-mono text-[10px] text-mist">{s.latency_ms}ms</span>
                  </div>
                  <p className="mt-0.5 text-xs text-mist">{s.message}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Evaluation + tests */}
        <Card className="p-6 lg:col-span-2">
          <h2 className="font-display text-xl font-500 italic">Evaluation</h2>
          <div className="mt-5 grid grid-cols-2 gap-x-8 gap-y-4">
            <EvalBar label="Test pass rate" value={ev.test_pass_rate || 0} color="#c6ff4a" />
            <EvalBar
              label="Retrieval P@k"
              value={ev.retrieval_precision_at_k || 0}
              color="#5ad1ff"
            />
            <EvalBar label="Tool success" value={ev.tool_success_rate || 0} color="#5affc4" />
            <EvalBar label="Composite score" value={ev.score || 0} color="#ff5b3a" />
          </div>
          <div className="mt-6 flex items-center gap-3 border-t hairline pt-4">
            <span className="font-mono text-[10px] uppercase tracking-widest text-mist">
              Task completed
            </span>
            <span className={ev.task_completed ? "text-acid" : "text-ember"}>
              {ev.task_completed ? "✓ yes" : "✗ needs review"}
            </span>
          </div>
          {d.test_runs.length > 0 && (
            <div className="mt-4 space-y-2">
              {d.test_runs.map((t, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between rounded-lg bg-ink-950 px-3 py-2 font-mono text-[11px]"
                >
                  <span className="text-mist">{t.command}</span>
                  <span className={t.passed ? "text-acid" : "text-ember"}>
                    {t.passed ? "PASS" : "FAIL"} · {t.total_tests} tests · iter {t.iteration}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Output tabs */}
      <Card className="overflow-hidden">
        <div className="flex border-b hairline">
          {(["diff", "summary", "context"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-6 py-3 font-mono text-xs uppercase tracking-widest transition-colors ${
                tab === t ? "bg-ink-850 text-bone" : "text-mist hover:text-bone"
              }`}
            >
              {t === "diff" ? "Patch" : t === "summary" ? "PR Summary" : "Retrieved Context"}
            </button>
          ))}
        </div>
        <div className="p-6">
          {tab === "diff" &&
            (d.diff.trim() ? (
              <DiffView diff={d.diff} />
            ) : (
              <p className="text-mist">No diff produced.</p>
            ))}
          {tab === "summary" && (
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-bone">
              {d.pr_summary || "No summary."}
            </pre>
          )}
          {tab === "context" && (
            <div className="space-y-2">
              {d.retrieved.map((c, i) => (
                <div key={i} className="flex items-center gap-3 font-mono text-[11px]">
                  <span className="text-acid tabular-nums">{c.score}</span>
                  <span className="text-bone">{c.file_path}</span>
                  <span className="text-mist">
                    :{c.start_line}-{c.end_line}
                  </span>
                  <span className="text-mist/60">{c.symbol || c.kind}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
