import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getHealth } from "./lib/api";
import PipelineHealth from "./screens/PipelineHealth";
import LiveEvents from "./screens/LiveEvents";
import DbtControls from "./screens/DbtControls";
import SqlExplorer from "./screens/SqlExplorer";

const tabs = [
  { to: "/health", label: "Pipeline Health" },
  { to: "/events", label: "Live Events" },
  { to: "/dbt", label: "dbt Controls" },
  { to: "/sql", label: "SQL Explorer" },
];

export default function App() {
  const { data } = useQuery({ queryKey: ["health"], queryFn: getHealth, refetchInterval: 10000 });
  const healthy = data?.status === "healthy";

  return (
    <div className="min-h-screen bg-bg-primary text-ink-primary">
      <nav className="h-[52px] bg-bg-card border-b border-line flex items-center px-4 gap-6">
        <div className="font-semibold whitespace-nowrap">
          ⚡ Pipeline Monitor <span className="text-ink-muted font-normal">v1.0</span>
        </div>
        <div className="flex gap-1">
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-md text-sm ${
                  isActive ? "bg-bg-secondary text-ink-primary" : "text-ink-secondary hover:bg-bg-secondary"
                }`
              }
            >
              {t.label}
            </NavLink>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-2 text-sm">
          <span className={`w-2 h-2 rounded-full ${data ? (healthy ? "bg-ok" : "bg-warn") : "bg-ink-muted"}`} />
          <span className="text-ink-secondary">
            {data ? (healthy ? "All systems healthy" : "Degraded") : "…"}
          </span>
        </div>
      </nav>

      <main className="p-5 max-w-6xl mx-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/health" replace />} />
          <Route path="/health" element={<PipelineHealth />} />
          <Route path="/events" element={<LiveEvents />} />
          <Route path="/dbt" element={<DbtControls />} />
          <Route path="/sql" element={<SqlExplorer />} />
        </Routes>
      </main>
    </div>
  );
}
