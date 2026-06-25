import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getLive,
  getRevenueByCity,
  getTopCustomers,
  getTopProducts,
  type RangeKey,
} from "./lib/api";

// One coherent palette (design tokens from SPEC §16).
const C = {
  revenue: "#0F6E56", // teal
  product: "#534AB7", // purple
  city: "#0F6E56",
  line: "#E5E3DC",
  axis: "#9B9895",
};
const STATUS_ORDER = ["pending", "processing", "shipped", "delivered"];
const STATUS_COLOR: Record<string, string> = {
  pending: "#D97706",
  processing: "#534AB7",
  shipped: "#0F6E56",
  delivered: "#16A34A",
};

const money = (n: any) =>
  "$" + Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });

const RANGES: { key: RangeKey; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "7d", label: "7 days" },
  { key: "30d", label: "30 days" },
  { key: "all", label: "All" },
];
const PREV_LABEL: Record<RangeKey, string> = {
  today: "yesterday",
  "7d": "prev 7d",
  "30d": "prev 30d",
  all: "",
};

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-bg-secondary ${className}`} />;
}

function Card({ title, action, children }: { title?: string; action?: any; children: any }) {
  return (
    <section className="bg-bg-card border border-line rounded-lg p-4">
      {title && (
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-medium">{title}</h2>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

function Kpi({ label, value, delta, prevLabel, sub, loading }: {
  label: string; value: string; delta?: number | null; prevLabel?: string; sub?: string; loading?: boolean;
}) {
  return (
    <div className="bg-bg-card border border-line rounded-lg p-4">
      <div className="text-sm text-ink-muted">{label}</div>
      {loading ? (
        <Skeleton className="h-7 w-24 mt-2" />
      ) : (
        <div className="text-2xl font-semibold mt-1">{value}</div>
      )}
      {!loading && delta != null ? (
        <div className={`text-xs mt-1 ${delta >= 0 ? "text-ok" : "text-danger"}`}>
          {delta >= 0 ? "▲" : "▼"} {Math.abs(delta)}% vs {prevLabel}
        </div>
      ) : !loading && sub ? (
        <div className="text-xs text-ink-muted mt-1">{sub}</div>
      ) : (
        <div className="text-xs mt-1">&nbsp;</div>
      )}
    </div>
  );
}

function Badge({ status }: { status: string }) {
  return (
    <span className="px-2 py-0.5 rounded text-xs font-medium capitalize"
      style={{ background: (STATUS_COLOR[status] ?? "#9B9895") + "1A", color: STATUS_COLOR[status] ?? "#6B6966" }}>
      {status}
    </span>
  );
}

export default function App() {
  const [range, setRange] = useState<RangeKey>("30d");
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [dayFilter, setDayFilter] = useState<string | null>(null);

  const live = useQuery({ queryKey: ["live", range], queryFn: () => getLive(range), refetchInterval: 5000 });
  const products = useQuery({ queryKey: ["top-products"], queryFn: getTopProducts, refetchInterval: 30000 });
  const cities = useQuery({ queryKey: ["revenue-by-city"], queryFn: getRevenueByCity, refetchInterval: 30000 });
  const customers = useQuery({ queryKey: ["top-customers"], queryFn: getTopCustomers, refetchInterval: 30000 });

  const data = live.data;
  const [ago, setAgo] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setAgo(Math.round((Date.now() - live.dataUpdatedAt) / 1000)), 1000);
    return () => clearInterval(id);
  }, [live.dataUpdatedAt]);

  const k = data?.kpis;
  const dl = data?.deltas;
  const prevLabel = PREV_LABEL[range];
  const realizedPct = k && k.revenue_usd ? Math.round((k.delivered_revenue / k.revenue_usd) * 100) : 0;

  const revChart = (data?.revenue_by_day ?? []).map((r) => ({
    date: String(r.date).slice(5), full: String(r.date), revenue: Number(r.revenue), orders: Number(r.orders),
  }));
  const statusMap: Record<string, number> = {};
  (data?.by_status ?? []).forEach((s) => (statusMap[s.status] = Number(s.orders)));
  const statusData = STATUS_ORDER.filter((s) => statusMap[s] != null).map((s) => ({ status: s, orders: statusMap[s] || 0 }));

  // Conversion funnel: cumulative orders that reached each stage (status only moves forward).
  const totalOrders = STATUS_ORDER.reduce((a, s) => a + (statusMap[s] || 0), 0);
  const funnel = STATUS_ORDER.map((stage, i) => {
    const reached = STATUS_ORDER.slice(i).reduce((a, s) => a + (statusMap[s] || 0), 0);
    return { stage, reached, pct: totalOrders ? Math.round((reached / totalOrders) * 100) : 0 };
  });

  // #12 drill-down: filter recent orders by clicked status and/or day.
  let recent = data?.recent_orders ?? [];
  if (statusFilter) recent = recent.filter((o) => o.status === statusFilter);
  if (dayFilter) recent = recent.filter((o) => String(o.created_at).slice(0, 10) === dayFilter);
  const filterActive = statusFilter || dayFilter;

  // #13 CSV export of the current revenue-by-day view.
  const exportCsv = () => {
    const rows = [["date", "orders", "revenue_usd"], ...(data?.revenue_by_day ?? []).map((r) => [r.date, r.orders, r.revenue])];
    const csv = rows.map((r) => r.join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url; a.download = `acme-revenue-${range}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen w-full bg-bg-primary text-ink-primary">
      <header className="bg-bg-card border-b border-line">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">Acme Shop · Executive overview</h1>
            <p className="text-sm text-ink-muted">Real-time analytics from the lakehouse</p>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className={`w-2 h-2 rounded-full ${data ? "bg-ok animate-pulse" : "bg-ink-muted"}`} />
            <span className="text-ink-secondary">
              {live.isError ? "Backend unreachable" : data ? `Live · updated ${ago}s ago` : "Connecting…"}
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm text-ink-muted mr-1">Period:</span>
          {RANGES.map((r) => (
            <button key={r.key} onClick={() => { setRange(r.key); setDayFilter(null); }}
              className={`px-3 py-1 rounded-md text-sm border ${range === r.key ? "bg-ink-primary text-white border-ink-primary" : "border-line text-ink-secondary hover:bg-bg-secondary"}`}>
              {r.label}
            </button>
          ))}
          <button onClick={exportCsv} className="ml-auto px-3 py-1 rounded-md text-sm border border-line text-ink-secondary hover:bg-bg-secondary">
            ⬇ Export CSV
          </button>
        </div>

        {/* KPIs: booked vs realized revenue (#10) + deltas (#4/#8) */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Kpi label="Total revenue (booked)" value={money(k?.revenue_usd)} delta={dl?.revenue_usd} prevLabel={prevLabel} loading={!data} />
          <Kpi label="Realized revenue (delivered)" value={money(k?.delivered_revenue)} sub={`${realizedPct}% of booked`} loading={!data} />
          <Kpi label="Total orders" value={String(k?.total_orders ?? 0)} delta={dl?.total_orders} prevLabel={prevLabel} loading={!data} />
          <Kpi label="Avg order value" value={money(k?.avg_order_value)} delta={dl?.avg_order_value} prevLabel={prevLabel} loading={!data} />
        </div>

        {/* Revenue trend — area chart (#2), click a day to drill down (#12) */}
        <Card title="Revenue by day">
          {!data ? <Skeleton className="h-64 w-full" /> : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={revChart} onClick={(e: any) => e?.activePayload && setDayFilter(e.activePayload[0].payload.full)}>
                  <defs>
                    <linearGradient id="rev" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={C.revenue} stopOpacity={0.35} />
                      <stop offset="100%" stopColor={C.revenue} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.line} />
                  <XAxis dataKey="date" fontSize={12} stroke={C.axis} />
                  <YAxis fontSize={12} stroke={C.axis} tickFormatter={(v) => money(v)} width={70} />
                  <Tooltip formatter={(v: any) => money(v)} labelFormatter={(l) => `Day ${l}`} />
                  <Area type="monotone" dataKey="revenue" stroke={C.revenue} strokeWidth={2} fill="url(#rev)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <div className="grid md:grid-cols-2 gap-6">
          {/* Conversion funnel (#11) */}
          <Card title="Conversion funnel">
            <div className="space-y-2">
              {funnel.map((f, i) => (
                <div key={f.stage}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="capitalize text-ink-secondary">{f.stage}</span>
                    <span className="text-ink-muted">
                      {f.reached} · {f.pct}%
                      {i > 0 && <span className="text-danger ml-1">(−{funnel[i - 1].pct - f.pct}%)</span>}
                    </span>
                  </div>
                  <div className="h-3 rounded bg-bg-secondary overflow-hidden">
                    <div className="h-full rounded" style={{ width: `${f.pct}%`, background: STATUS_COLOR[f.stage] }} />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Order status mix donut (#9), click to filter recent orders (#12) */}
          <Card title="Order status mix">
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={statusData} dataKey="orders" nameKey="status" innerRadius={45} outerRadius={70}
                    onClick={(e: any) => setStatusFilter(statusFilter === e.status ? null : e.status)}>
                    {statusData.map((s) => (
                      <Cell key={s.status} fill={STATUS_COLOR[s.status]} cursor="pointer"
                        opacity={statusFilter && statusFilter !== s.status ? 0.35 : 1} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-wrap gap-3 justify-center text-sm">
              {statusData.map((s) => (
                <button key={s.status} onClick={() => setStatusFilter(statusFilter === s.status ? null : s.status)}
                  className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: STATUS_COLOR[s.status] }} />
                  <span className="capitalize text-ink-secondary">{s.status}</span>
                  <span className="font-medium">{s.orders}</span>
                </button>
              ))}
            </div>
          </Card>

          {/* Top products (#9) */}
          <Card title="Top products by revenue">
            {!products.data ? <Skeleton className="h-48 w-full" /> : (
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={products.data.slice(0, 6).map((p: any) => ({ name: String(p.product_name), revenue: Number(p.revenue_usd) }))} layout="vertical" margin={{ left: 10 }}>
                    <XAxis type="number" fontSize={11} stroke={C.axis} tickFormatter={(v) => money(v)} />
                    <YAxis type="category" dataKey="name" fontSize={11} width={110} stroke={C.axis} />
                    <Tooltip formatter={(v: any) => money(v)} />
                    <Bar dataKey="revenue" fill={C.product} radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>

          {/* Revenue by city (#9) */}
          <Card title="Revenue by city">
            {!cities.data ? <Skeleton className="h-48 w-full" /> : (
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={cities.data.slice(0, 6).map((c: any) => ({ city: String(c.city), revenue: Number(c.revenue_usd) }))}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.line} />
                    <XAxis dataKey="city" fontSize={11} stroke={C.axis} />
                    <YAxis fontSize={11} stroke={C.axis} tickFormatter={(v) => money(v)} width={60} />
                    <Tooltip formatter={(v: any) => money(v)} />
                    <Bar dataKey="revenue" fill={C.city} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>

          {/* Top customers (#9) */}
          <Card title="Top customers by lifetime value">
            <div className="divide-y divide-line">
              {(customers.data ?? []).slice(0, 8).map((c: any, i: number) => (
                <div key={i} className="flex items-center py-2 text-sm">
                  <span className="w-5 text-ink-muted">{i + 1}</span>
                  <span className="font-medium">{c.name}</span>
                  <span className="text-ink-muted ml-2">{c.city}</span>
                  <span className="ml-auto font-semibold">{money(c.lifetime_value_usd)}</span>
                </div>
              ))}
              {(customers.data ?? []).length === 0 && <div className="text-ink-muted text-sm py-2">No delivered orders yet</div>}
            </div>
          </Card>

          {/* Recent orders + drill-down (#12) */}
          <Card title="Recent orders" action={filterActive && (
            <button onClick={() => { setStatusFilter(null); setDayFilter(null); }} className="text-xs text-teal underline">
              Clear filter{dayFilter ? ` (${dayFilter})` : statusFilter ? ` (${statusFilter})` : ""}
            </button>
          )}>
            <div className="divide-y divide-line max-h-72 overflow-y-auto pr-1">
              {recent.map((o) => (
                <div key={o.id} className="flex items-center gap-3 py-2 text-sm">
                  <span className="font-mono text-ink-muted w-14">#{o.id}</span>
                  <Badge status={o.status} />
                  <span className="text-ink-muted ml-auto">{String(o.created_at).slice(5, 16)}</span>
                  <span className="font-semibold w-20 text-right">{money(o.amount)}</span>
                </div>
              ))}
              {recent.length === 0 && <div className="text-ink-muted text-sm py-2">No matching orders</div>}
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
}
