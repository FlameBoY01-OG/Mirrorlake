import { useState } from "react";
import { runQuery, type QueryResult } from "../lib/api";

const DEFAULT_SQL = "SELECT * FROM iceberg.shop.daily_revenue ORDER BY date DESC LIMIT 20";

export default function SqlExplorer() {
  const [sql, setSql] = useState(DEFAULT_SQL);
  const [res, setRes] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    try {
      setRes(await runQuery(sql));
    } catch (e: any) {
      setRes({ columns: [], rows: [], row_count: 0, duration_ms: 0, error: String(e) });
    }
    setLoading(false);
  };

  const onKey = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") run();
  };

  const exportCsv = () => {
    if (!res) return;
    const csv = [
      res.columns.join(","),
      ...res.rows.map((r) => r.map((c) => JSON.stringify(c ?? "")).join(",")),
    ].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "query.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <h1 className="text-lg font-semibold mb-4">SQL Explorer</h1>
      <textarea
        value={sql}
        onChange={(e) => setSql(e.target.value)}
        onKeyDown={onKey}
        spellCheck={false}
        className="w-full h-32 font-mono text-sm p-3 rounded-lg bg-ink-primary text-white outline-none"
      />
      <div className="flex items-center gap-3 mt-2 mb-4">
        <button
          onClick={run}
          disabled={loading}
          className="px-4 py-1.5 rounded-md bg-teal text-white text-sm disabled:opacity-50"
        >
          {loading ? "Running…" : "Run (Ctrl+Enter)"}
        </button>
        {res && !res.error && (
          <span className="text-sm text-ink-muted">
            {res.row_count} rows · {res.duration_ms}ms
          </span>
        )}
        {res && !res.error && res.row_count > 0 && (
          <button onClick={exportCsv} className="text-sm text-teal underline">
            Export CSV
          </button>
        )}
      </div>

      {res?.error && (
        <div className="bg-danger/10 text-danger text-sm p-3 rounded-lg font-mono whitespace-pre-wrap">{res.error}</div>
      )}
      {res && !res.error && (
        <div className="overflow-auto border border-line rounded-lg">
          <table className="w-full text-sm">
            <thead className="bg-bg-secondary">
              <tr>
                {res.columns.map((c) => (
                  <th key={c} className="text-left px-3 py-2 font-medium whitespace-nowrap">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {res.rows.map((r, i) => (
                <tr key={i} className="border-t border-line">
                  {r.map((c, j) => (
                    <td key={j} className="px-3 py-1.5 font-mono text-ink-secondary whitespace-nowrap">{String(c)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
