"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui";

export default function SettingsPage() {
  const [health, setHealth] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setErr(String(e)));
  }, []);

  const Row = ({ k, v }: { k: string; v: React.ReactNode }) => (
    <div className="flex items-center justify-between border-b hairline py-3 last:border-0">
      <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-mist">{k}</span>
      <span className="font-mono text-sm text-bone">{v}</span>
    </div>
  );

  return (
    <div className="space-y-10">
      <header className="rise">
        <div className="font-mono text-xs uppercase tracking-[0.3em] text-ember">Runtime</div>
        <h1 className="mt-2 font-display text-5xl font-600 italic tracking-tight">Settings</h1>
        <p className="mt-3 max-w-xl text-mist">
          DevPilot runs in one of three modes. Switch by setting the{" "}
          <code className="text-bone">DEVPILOT_MODE</code> environment variable before starting the
          backend.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <Card className="p-6">
          <h2 className="font-display text-xl font-500 italic">Backend status</h2>
          <div className="mt-4">
            {err && <p className="font-mono text-xs text-ember">Unreachable: {err}</p>}
            {health && (
              <>
                <Row k="Status" v={<span className="text-acid">{health.status}</span>} />
                <Row k="Mode" v={health.mode} />
                <Row k="Database" v={health.database} />
                <Row k="Repos" v={health.repos} />
                <Row k="Runs" v={health.runs} />
              </>
            )}
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="font-display text-xl font-500 italic">Run modes</h2>
          <div className="mt-4 space-y-4">
            <div>
              <div className="font-mono text-xs uppercase tracking-widest text-acid">mock</div>
              <p className="mt-1 text-sm text-mist">
                Deterministic agents. No LLM, no external services. Real file ops, git diffs, and
                pytest runs. Best for demos and CI.
              </p>
            </div>
            <div>
              <div className="font-mono text-xs uppercase tracking-widest text-azure">local</div>
              <p className="mt-1 text-sm text-mist">
                Uses Ollama at <code className="text-bone">localhost:11434</code> with a local code
                model.
              </p>
            </div>
            <div>
              <div className="font-mono text-xs uppercase tracking-widest text-ember">api</div>
              <p className="mt-1 text-sm text-mist">
                Uses a hosted provider (OpenAI / Anthropic) when an API key is set.
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
