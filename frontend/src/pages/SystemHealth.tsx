import { useQuery } from "@tanstack/react-query";
import { getHealth, getRawMetricsText } from "../api/health";
import { ErrorNotice } from "../components/ErrorNotice";
import { StatCard } from "../components/StatCard";
import { formatCount } from "../utils/format";
import { summarizeMetrics } from "../utils/prometheus";

const GRAFANA_URL = "http://localhost:3000";
const PROMETHEUS_URL = "http://localhost:9090";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Couldn't reach the server.";
}

export function SystemHealth() {
  const healthQuery = useQuery({
    queryKey: ["system-health", "healthz"],
    queryFn: () => getHealth(),
    refetchInterval: 15_000,
  });
  const metricsQuery = useQuery({
    queryKey: ["system-health", "metrics"],
    queryFn: () => getRawMetricsText(),
    refetchInterval: 15_000,
  });

  const summary = metricsQuery.data ? summarizeMetrics(metricsQuery.data) : null;
  const isUp = healthQuery.data?.status === "ok";

  return (
    <div className="page">
      <div className="page-header">
        <h1>System Health</h1>
        <p className="text-muted">Live status from GET /healthz and the Prometheus /metrics endpoint.</p>
      </div>

      <div className="panel">
        <h2>API Status</h2>
        {healthQuery.isLoading && <div className="page-loading">Checking…</div>}
        {healthQuery.isError && <ErrorNotice message={errorMessage(healthQuery.error)} />}
        {healthQuery.data && (
          <p>
            <span className={"status-dot " + (isUp ? "status-dot-ok" : "status-dot-down")} />
            {isUp ? "Backend is healthy" : `Unexpected status: ${healthQuery.data.status}`}
          </p>
        )}
      </div>

      <div className="panel">
        <h2>Metrics Snapshot</h2>
        <p className="text-muted">Parsed from the raw Prometheus text exposition format.</p>
        {metricsQuery.isLoading && <div className="page-loading">Loading metrics…</div>}
        {metricsQuery.isError && <ErrorNotice message={errorMessage(metricsQuery.error)} />}
        {summary && (
          <div className="stat-grid">
            <StatCard label="Total LLM Requests" value={formatCount(summary.totalLlmRequests)} />
            <StatCard label="Total LLM Errors" value={formatCount(summary.totalLlmErrors)} />
            <StatCard label="Cache Hits" value={formatCount(summary.cacheHits)} />
            <StatCard label="Cache Misses" value={formatCount(summary.cacheMisses)} />
            <StatCard label="Total HTTP Requests" value={formatCount(summary.totalHttpRequests)} />
          </div>
        )}
      </div>

      <div className="panel">
        <h2>Dashboards</h2>
        <p className="text-muted">
          Full Grafana dashboards and raw Prometheus queries live outside this app.
        </p>
        <div className="link-row">
          <a
            className="external-link-card"
            href={GRAFANA_URL}
            target="_blank"
            rel="noreferrer"
          >
            <span className="external-link-card-title">Grafana →</span>
            <span className="external-link-card-hint">{GRAFANA_URL}</span>
          </a>
          <a
            className="external-link-card"
            href={PROMETHEUS_URL}
            target="_blank"
            rel="noreferrer"
          >
            <span className="external-link-card-title">Prometheus →</span>
            <span className="external-link-card-hint">{PROMETHEUS_URL}</span>
          </a>
        </div>
      </div>
    </div>
  );
}
