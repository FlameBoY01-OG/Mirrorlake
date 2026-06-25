import { useMutation, useQuery } from "@tanstack/react-query";
import { getDbtStatus, runDbt } from "../lib/api";

export default function DbtControls() {
  const { data } = useQuery({
    queryKey: ["dbt-status"],
    queryFn: getDbtStatus,
    refetchInterval: 2000,
  });
  const mut = useMutation({ mutationFn: runDbt });
  const running = data?.status === "running" || mut.isPending;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold">dbt Controls</h1>
        <button
          disabled={running}
          onClick={() => mut.mutate()}
          className="px-4 py-1.5 rounded-md bg-teal text-white text-sm disabled:opacity-50"
        >
          {running ? "Running…" : "Run dbt now"}
        </button>
      </div>

      <div className="bg-bg-card border border-line rounded-lg divide-y divide-line mb-4">
        {(data?.models ?? []).length === 0 && (
          <div className="p-4 text-ink-muted text-sm">No runs yet. Click “Run dbt now”.</div>
        )}
        {(data?.models ?? []).map((m, i) => (
          <div key={i} className="flex items-center px-3 py-2 text-sm">
            <span
              className={`w-2 h-2 rounded-full mr-2 ${
                m.status === "success" || m.status === "pass" ? "bg-ok" : "bg-danger"
              }`}
            />
            <span className="font-mono">{m.name}</span>
            <span className="ml-auto text-ink-muted">
              {m.status} · {m.execution_time}s
            </span>
          </div>
        ))}
      </div>

      {data?.log && (
        <details className="bg-bg-card border border-line rounded-lg">
          <summary className="px-3 py-2 text-sm cursor-pointer text-ink-secondary">Raw dbt output</summary>
          <pre className="text-xs p-3 overflow-auto max-h-80 bg-ink-primary text-white rounded-b-lg whitespace-pre-wrap">
            {data.log}
          </pre>
        </details>
      )}
    </div>
  );
}
