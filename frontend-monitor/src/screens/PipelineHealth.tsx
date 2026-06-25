import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getHealth } from "../lib/api";

const dot = (s: string) =>
  s === "up" ? "bg-ok" : s === "degraded" ? "bg-warn" : "bg-danger";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-bg-card border border-line rounded-lg p-3">
      <div className="text-xs text-ink-muted">{label}</div>
      <div className="text-xl font-semibold mt-1">{value}</div>
    </div>
  );
}

export default function PipelineHealth() {
  const { data, dataUpdatedAt } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 10000,
  });
  const [ago, setAgo] = useState(0);

  useEffect(() => {
    const id = setInterval(
      () => setAgo(Math.round((Date.now() - dataUpdatedAt) / 1000)),
      1000
    );
    return () => clearInterval(id);
  }, [dataUpdatedAt]);

  if (!data) return <div className="text-ink-muted">Loading…</div>;
  const s = data.stats;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold">Pipeline Health</h1>
        <span className="text-sm text-ink-muted">last checked {ago}s ago</span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        {Object.entries(data.services).map(([name, v]) => (
          <div key={name} className="bg-bg-card border border-line rounded-lg p-3">
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${dot(v.status)}`} />
              <span className="font-medium capitalize">{name.replace("_", " ")}</span>
            </div>
            <div className="text-sm text-ink-muted mt-1 truncate">
              {v.state || v.detail || v.status}
              {v.topics != null ? ` · ${v.topics} topics` : ""}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat
          label="End-to-end latency"
          value={s.end_to_end_latency_ms != null ? `${(s.end_to_end_latency_ms / 1000).toFixed(1)}s` : "—"}
        />
        <Stat label="Events today" value={s.events_today.toLocaleString()} />
        <Stat label="Iceberg snapshots" value={s.snapshot_count != null ? String(s.snapshot_count) : "—"} />
        <Stat label="Last dbt run" value={s.last_dbt_run.status} />
      </div>
    </div>
  );
}
