import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import { getRequestsSummary, listRequests } from "../api/requests";
import { ErrorNotice } from "../components/ErrorNotice";
import { StatCard } from "../components/StatCard";
import type { LLMRequestRead } from "../api/types";
import { formatCount, formatCurrency, formatLatency, formatPercent, parseDecimal } from "../utils/format";

const CHART_SAMPLE_SIZE = 200;

function bucketByHour(requests: LLMRequestRead[]): { time: string; count: number }[] {
  const buckets = new Map<string, number>();
  for (const request of requests) {
    const bucketStart = new Date(request.created_at);
    bucketStart.setMinutes(0, 0, 0);
    const key = bucketStart.toISOString();
    buckets.set(key, (buckets.get(key) ?? 0) + 1);
  }
  return Array.from(buckets.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, count]) => ({
      time: new Date(key).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      count,
    }));
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Couldn't reach the server.";
}

export function Dashboard() {
  const summaryQuery = useQuery({
    queryKey: ["requests", "summary"],
    queryFn: () => getRequestsSummary(),
  });
  const listQuery = useQuery({
    queryKey: ["requests", { limit: CHART_SAMPLE_SIZE }],
    queryFn: () => listRequests(CHART_SAMPLE_SIZE),
  });

  const chartData = useMemo(() => bucketByHour(listQuery.data ?? []), [listQuery.data]);
  const summary = summaryQuery.data;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Dashboard</h1>
        <p className="text-muted">
          Live summary across all of your requests; chart shows the most recent {CHART_SAMPLE_SIZE}.
        </p>
      </div>

      {summaryQuery.isError && <ErrorNotice message={errorMessage(summaryQuery.error)} />}
      {summaryQuery.isLoading && <div className="page-loading">Loading dashboard…</div>}

      {summary && (
        <div className="stat-grid">
          <StatCard label="Total Requests" value={formatCount(summary.total_requests)} />
          <StatCard label="Success Rate" value={formatPercent(summary.success_rate)} />
          <StatCard
            label="Average Latency"
            value={
              summary.average_latency_ms === null ? "—" : formatLatency(summary.average_latency_ms)
            }
          />
          <StatCard label="Total Tokens" value={formatCount(summary.total_tokens)} />
          <StatCard
            label="Estimated Cost"
            value={formatCurrency(parseDecimal(summary.total_cost))}
          />
          <StatCard label="Cache Hit Rate" value={formatPercent(summary.cache_hit_rate)} />
        </div>
      )}

      <div className="panel">
        <h2>Requests Over Time</h2>
        {listQuery.isError ? (
          <div className="empty-state empty-state-inline">
            <p>Couldn't load request history for this chart.</p>
          </div>
        ) : chartData.length === 0 ? (
          <div className="empty-state empty-state-inline">
            <p>No request data to chart yet.</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="time" stroke="var(--text-muted)" fontSize={12} />
              <YAxis allowDecimals={false} stroke="var(--text-muted)" fontSize={12} />
              <Tooltip
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                }}
              />
              <Line
                type="monotone"
                dataKey="count"
                name="Requests"
                stroke="var(--accent)"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
