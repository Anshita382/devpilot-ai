"use client";

export function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    completed: "text-acid border-acid/30 bg-acid/10",
    ready: "text-acid border-acid/30 bg-acid/10",
    running: "text-azure border-azure/30 bg-azure/10",
    needs_review: "text-ember border-ember/30 bg-ember/10",
    error: "text-ember border-ember/30 bg-ember/10",
  };
  const cls = map[status] || "text-mist border-mist/30 bg-mist/10";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-widest ${cls}`}>
      {status === "running" && <span className="h-1.5 w-1.5 rounded-full bg-azure pulse-dot" />}
      {status.replace("_", " ")}
    </span>
  );
}

const AGENT_COLORS: Record<string, string> = {
  planner: "#5ad1ff",
  retrieval: "#c6ff4a",
  coder: "#ff5b3a",
  tester: "#ffb84a",
  reviewer: "#b78bff",
  evaluator: "#5affc4",
};

export function agentColor(agent: string): string {
  return AGENT_COLORS[agent] || "#9aa0b4";
}

export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-xl border hairline bg-ink-900/60 ${className}`}>{children}</div>
  );
}
