"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Repo } from "@/lib/api";
import { Card, StatusPill } from "@/components/ui";

export default function ReposPage() {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [url, setUrl] = useState("../examples/sample-fastapi-repo");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = () => api.listRepos().then(setRepos).catch((e) => setErr(String(e)));
  useEffect(() => {
    load();
  }, []);

  async function ingest() {
    setBusy(true);
    setErr(null);
    try {
      await api.ingest(url);
      setUrl("");
      await load();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-10">
      <header className="rise">
        <div className="font-mono text-xs uppercase tracking-[0.3em] text-ember">Index</div>
        <h1 className="mt-2 font-display text-5xl font-600 italic tracking-tight">Repositories</h1>
        <p className="mt-3 max-w-xl text-mist">
          Ingest a Git URL or a local path. The pipeline chunks code AST-aware, embeds it, and builds
          a hybrid (dense + BM25) index.
        </p>
      </header>

      <Card className="p-5 rise">
        <label className="font-mono text-[10px] uppercase tracking-[0.25em] text-mist">
          Repository URL or local path
        </label>
        <div className="mt-3 flex gap-3">
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://github.com/user/repo  ·  or  ·  ../examples/sample-fastapi-repo"
            className="flex-1 rounded-lg border hairline bg-ink-950 px-4 py-3 font-mono text-sm text-bone outline-none placeholder:text-mist/50 focus:border-azure/50"
          />
          <button
            onClick={ingest}
            disabled={busy || !url.trim()}
            className="rounded-lg bg-ember px-6 py-3 font-mono text-xs uppercase tracking-widest text-ink-950 transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {busy ? "Ingesting…" : "Ingest"}
          </button>
        </div>
        {err && <p className="mt-3 font-mono text-xs text-ember">{err}</p>}
      </Card>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {repos.map((r) => (
          <Link key={r.id} href={`/repos/${r.id}`}>
            <Card className="group p-5 transition-colors hover:border-azure/40">
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-display text-xl font-500 text-bone group-hover:text-azure">
                    {r.name}
                  </div>
                  <div className="mt-1 truncate font-mono text-xs text-mist">{r.url}</div>
                </div>
                <StatusPill status={r.status} />
              </div>
              <div className="mt-5 flex gap-6 font-mono text-xs text-mist">
                <span>
                  <span className="text-bone">{r.n_files}</span> files
                </span>
                <span>
                  <span className="text-bone">{r.n_chunks}</span> chunks
                </span>
                <span className="text-acid">{r.language}</span>
              </div>
            </Card>
          </Link>
        ))}
      </section>
    </div>
  );
}
