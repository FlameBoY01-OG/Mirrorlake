const env = (import.meta as any).env || {};
const API = env.VITE_API_URL || "http://localhost:8000";

interface QueryResult {
  columns: string[];
  rows: any[][];
  row_count: number;
  duration_ms: number;
  error: string | null;
}

// Backend /metrics/* return Trino result envelopes; flatten to objects keyed by column.
async function getMetric(path: string): Promise<Record<string, any>[]> {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(`${path} → HTTP ${r.status}`);
  const d: QueryResult = await r.json();
  if (d.error) throw new Error(d.error);
  return d.rows.map((row) => Object.fromEntries(d.columns.map((c, i) => [c, row[i]])));
}

export const getRevenue = () => getMetric("/metrics/revenue");
export const getFunnel = () => getMetric("/metrics/funnel");
export const getTopCustomers = () => getMetric("/metrics/top-customers");
export const getTopProducts = () => getMetric("/metrics/top-products");
export const getRevenueByCity = () => getMetric("/metrics/revenue-by-city");

export type RangeKey = "today" | "7d" | "30d" | "all";

export interface LiveMetrics {
  range: string;
  kpis: {
    revenue_usd: number;
    total_orders: number;
    avg_order_value: number;
    delivered_revenue: number;
    delivered_orders: number;
    buying_customers: number;
    active_customers: number;
  };
  deltas: {
    revenue_usd: number | null;
    total_orders: number | null;
    avg_order_value: number | null;
  };
  by_status: { status: string; orders: number; revenue: number }[];
  revenue_by_day: { date: string; orders: number; revenue: number }[];
  recent_orders: { id: number; status: string; amount: number; created_at: string }[];
}

export async function getLive(range: RangeKey = "30d"): Promise<LiveMetrics> {
  const r = await fetch(`${API}/metrics/live?range=${range}`);
  if (!r.ok) throw new Error(`/metrics/live → HTTP ${r.status}`);
  return r.json();
}
