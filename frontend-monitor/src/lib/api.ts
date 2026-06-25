const env = (import.meta as any).env || {};
const API = env.VITE_API_URL || "http://localhost:8000";
export const WS_URL = (env.VITE_WS_URL || "ws://localhost:8000") + "/events/stream";

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(API + path, init);
  if (!r.ok) throw new Error(`${path} → HTTP ${r.status}`);
  return r.json();
}

export interface ServiceStatus {
  status: string;
  detail?: string;
  state?: string;
  topics?: number;
  [k: string]: any;
}
export interface Health {
  status: string;
  services: Record<string, ServiceStatus>;
  stats: {
    end_to_end_latency_ms: number | null;
    events_today: number;
    events_total: number;
    snapshot_count: number | null;
    last_dbt_run: { status: string; finished_at: string | null };
  };
}
export interface CdcEvent {
  _seq: number;
  table: string;
  op: string;
  latency_ms: number | null;
  received_ms: number;
  data: Record<string, any>;
}
export interface QueryResult {
  columns: string[];
  rows: any[][];
  row_count: number;
  duration_ms: number;
  error: string | null;
}
export interface DbtModel { name: string; status: string; execution_time: number }
export interface DbtStatus {
  job_id: string | null;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  models: DbtModel[];
  log: string;
}

export const getHealth = () => j<Health>("/health");
export const getEvents = () => j<{ events: CdcEvent[] }>("/events");
export const runQuery = (sql: string) =>
  j<QueryResult>("/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sql }),
  });
export const runDbt = () => j<{ job_id: string; status: string }>("/dbt/run", { method: "POST" });
export const getDbtStatus = () => j<DbtStatus>("/dbt/status");
