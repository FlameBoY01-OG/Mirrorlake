import { useState } from "react";
import { useEventStream } from "../lib/useEventStream";

const OPS: Record<string, { label: string; cls: string }> = {
  c: { label: "INSERT", cls: "bg-purple/10 text-purple" },
  r: { label: "SNAPSHOT", cls: "bg-ink-muted/20 text-ink-secondary" },
  u: { label: "UPDATE", cls: "bg-teal/10 text-teal" },
  d: { label: "DELETE", cls: "bg-coral/10 text-coral" },
};
const FILTERS = ["ALL", "INSERT", "UPDATE", "DELETE"];

export default function LiveEvents() {
  const { events, connected } = useEventStream(150);
  const [filter, setFilter] = useState("ALL");
  const shown = events.filter((e) => filter === "ALL" || OPS[e.op]?.label === filter);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold">Live Events</h1>
        <div className="flex items-center gap-2 text-sm">
          <span className={`w-2 h-2 rounded-full ${connected ? "bg-ok animate-pulse" : "bg-ink-muted"}`} />
          <span className="text-ink-secondary">{connected ? "Live" : "Connecting…"}</span>
        </div>
      </div>

      <div className="flex gap-2 mb-3">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-full text-xs border ${
              filter === f ? "bg-ink-primary text-white border-ink-primary" : "border-line text-ink-secondary"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="bg-bg-card border border-line rounded-lg divide-y divide-line">
        {shown.length === 0 && <div className="p-4 text-ink-muted text-sm">Waiting for events…</div>}
        {shown.map((e) => {
          const op = OPS[e.op] || { label: e.op, cls: "bg-ink-muted/10" };
          return (
            <div key={e._seq} className="flex items-center gap-3 px-3 py-2 text-sm">
              <span className="text-ink-muted w-20 shrink-0">{new Date(e.received_ms).toLocaleTimeString()}</span>
              <span className={`px-2 py-0.5 rounded text-xs font-medium shrink-0 w-20 text-center ${op.cls}`}>
                {op.label}
              </span>
              <span className="font-mono text-ink-secondary w-28 shrink-0">{e.table}</span>
              <span className="font-mono text-xs text-ink-muted truncate">{JSON.stringify(e.data)}</span>
              {e.latency_ms != null && <span className="ml-auto text-xs text-ink-muted shrink-0">{e.latency_ms}ms</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
