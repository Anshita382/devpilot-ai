"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, Repo } from "@/lib/api";
import { Card, StatusPill } from "@/components/ui";

const SUGGESTED = [
  "Add a health check endpoint",
  "Add Redis caching to the product search API",
  "Add input validation to the search endpoint",
  "Add pagination to the product list endpoint",
];

export default function RepoDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);

  const [repo, setRepo] = useState<Repo | null>(null);
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState<{ answer: string; chunks: any[] } | null>(null);
  const [chatBusy, setChatBusy] = useState(false);
  const [task, setTask] = useState(SUGGESTED[0]);
  const [runBusy, setRunBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.getRepo(id).then(setRepo).catch((e) => setErr(String(e)));
  }, [id]);

  async function ask() {
    if (!query.trim()) return;
    setChatBusy(true);
    try {
      setAnswer(await api.chat(id, query));
    } catch (e) {
      setErr(String(e));
    } finally {
      setChatBusy(false);
    }
  }

  async function run() {
    setRunBusy(true);
    setErr(null);
    try {
      const detail = await api.runAgent(id, task);
      router.push(`/agents/${detail.run.id}`);
    } catch (e) {
      setErr(String(e));
      setRunBusy(false);
    }
  }

  if (!repo) return <div className="text-mist">Loading…</div>;

  return (
    <div className="space-y-10">
      <header className="rise flex items-end justify-between">
        <div>
          <div className="font-mono text-xs uppercase tracking-[0.3em] text-ember">Repository</div>
          <h1 className="mt-2 font-display text-5xl font-600 italic tracking-tight">{repo.name}</h1>
          <div className="mt-3 flex gap-6 font-mono text-xs text-mist">
            <span>
              <span className="text-bone">{repo.n_files}</span> files
            </span>
            <span>
              <span className="text-bone">{repo.n_chunks}</span> chunks
            </span>
            <span className="text-acid">{repo.language}</span>
          </div>
        </div>
        <StatusPill status={repo.status} />
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Agent run launcher */}
        <Card className="p-6">
          <h2 className="font-display text-2xl font-500 italic">Run an agent task</h2>
          <p className="mt-2 text-sm text-mist">
            The full six-agent workflow will plan, retrieve context, write code, run tests
            (self-healing on failure), review, and score the result.
          </p>
          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            rows={3}
            className="mt-4 w-full rounded-lg border hairline bg-ink-950 px-4 py-3 text-sm text-bone outline-none focus:border-ember/50"
          />
          <div className="mt-3 flex flex-wrap gap-2">
            {SUGGESTED.map((s) => (
              <button
                key={s}
                onClick={() => setTask(s)}
                className="rounded-full border hairline px-3 py-1 font-mono text-[10px] uppercase tracking-widest text-mist transition-colors hover:border-ember/40 hover:text-bone"
              >
                {s.replace("Add ", "")}
              </button>
            ))}
          </div>
          <button
            onClick={run}
            disabled={runBusy}
            className="mt-5 w-full rounded-lg bg-ember py-3 font-mono text-xs uppercase tracking-widest text-ink-950 transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {runBusy ? "Running pipeline…" : "Launch workflow"}
          </button>
        </Card>

        {/* RAG chat */}
        <Card className="p-6">
          <h2 className="font-display text-2xl font-500 italic">Ask the codebase</h2>
          <p className="mt-2 text-sm text-mist">
            Hybrid retrieval over the indexed chunks, with grounded citations.
          </p>
          <div className="mt-4 flex gap-3">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && ask()}
              placeholder="How does product search work?"
              className="flex-1 rounded-lg border hairline bg-ink-950 px-4 py-3 text-sm text-bone outline-none placeholder:text-mist/50 focus:border-azure/50"
            />
            <button
              onClick={ask}
              disabled={chatBusy}
              className="rounded-lg border border-azure/40 px-5 font-mono text-xs uppercase tracking-widest text-azure transition-colors hover:bg-azure/10 disabled:opacity-40"
            >
              {chatBusy ? "…" : "Ask"}
            </button>
          </div>
          {answer && (
            <div className="mt-5 space-y-4">
              <div className="whitespace-pre-wrap rounded-lg bg-ink-950 p-4 text-sm leading-relaxed text-bone">
                {answer.answer}
              </div>
              <div className="space-y-1.5">
                {answer.chunks.slice(0, 5).map((c, i) => (
                  <div key={i} className="flex items-center gap-3 font-mono text-[11px] text-mist">
                    <span className="text-acid">{c.score}</span>
                    <span className="text-bone">{c.file_path}</span>
                    <span>:{c.start_line}-{c.end_line}</span>
                    <span className="text-mist/60">{c.symbol || c.kind}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>

      {err && <p className="font-mono text-xs text-ember">{err}</p>}
    </div>
  );
}
