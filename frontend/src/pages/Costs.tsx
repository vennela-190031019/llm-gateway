import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getCostByModel, getRequestsSummary, listRequests } from "../api/requests";
import type { LLMRequestRead } from "../api/types";
import { ErrorNotice } from "../components/ErrorNotice";
import { StatCard } from "../components/StatCard";
import { formatCount, formatCurrency, parseDecimal } from "../utils/format";

const CHART_SAMPLE_SIZE = 200;

interface CostBucket {
  time: string;
  cost: number;
}

function bucketCostByHour(requests: LLMRequestRead[]): CostBucket[] {
  const buckets = new Map<string, number>();
  for (const request of requests) {
    const bucketStart = new Date(request.created_at);
    bucketStart.setMinutes(0, 0, 0);
    const key = bucketStart.toISOString();
    const cost = parseDecimal(request.estimated_cost) ?? 0;
    buckets.set(key, (buckets.get(key) ?? 0) + cost);
  }
  return Array.from(buckets.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, cost]) => ({
      time: new Date(key).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      cost: Math.round(cost * 1e6) / 1e6,
    }));
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Couldn't reach the server.";
}

export function Costs() {
  const summaryQuery = useQuery({
    queryKey: ["requests", "summary"],
    queryFn: () => getRequestsSummary(),
  });
  const costByModelQuery = useQuery({
    queryKey: ["requests", "cost-by-model"],
    queryFn: () => getCostByModel(),
  });
  const listQuery = useQuery({
    queryKey: ["requests", { limit: CHART_SAMPLE_SIZE }],
    queryFn: () => listRequests(CHART_SAMPLE_SIZE),
  });

  const costByModelChartData = useMemo(
    () =>
      (costByModelQuery.data ?? []).map((row) => ({
        model: row.model,
        cost: parseDecimal(row.total_cost) ?? 0,
      })),
    [costByModelQuery.data],
  );
  const costOverTimeData = useMemo(
    () => bucketCostByHour(listQuery.data ?? []),
    [listQuery.data],
  );

  const summary = summaryQuery.data;
  const totalCost = summary ? parseDecimal(summary.total_cost) : null;
  const avgCostPerRequest =
    summary && summary.total_requests > 0 && totalCost !== null
      ? totalCost / summary.total_requests
      : null;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Costs</h1>
        <p className="text-muted">
          Total cost and cost-by-model are exact (all requests); the trend chart samples the
          most recent {CHART_SAMPLE_SIZE}.
        </p>
      </div>

      {summaryQuery.isError && <ErrorNotice message={errorMessage(summaryQuery.error)} />}
      {costByModelQuery.isError && <ErrorNotice message={errorMessage(costByModelQuery.error)} />}

      <div className="stat-grid">
        <StatCard label="Total Cost" value={formatCurrency(totalCost)} />
        <StatCard
          label="Total Requests"
          value={summary ? formatCount(summary.total_requests) : "—"}
        />
        <StatCard label="Avg Cost / Request" value={formatCurrency(avgCostPerRequest)} />
      </div>

      <div className="panel">
        <h2>Cost by Model</h2>
        {costByModelChartData.length === 0 ? (
          <div className="empty-state empty-state-inline">
            <p>No cost data yet.</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={costByModelChartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="model" stroke="var(--text-muted)" fontSize={12} />
              <YAxis stroke="var(--text-muted)" fontSize={12} />
              <Tooltip
                formatter={(value: number) => formatCurrency(value)}
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                }}
              />
              <Bar dataKey="cost" name="Cost" fill="var(--accent)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="panel">
        <h2>Cost Over Time</h2>
        {costOverTimeData.length === 0 ? (
          <div className="empty-state empty-state-inline">
            <p>No cost data to chart yet.</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={costOverTimeData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="time" stroke="var(--text-muted)" fontSize={12} />
              <YAxis stroke="var(--text-muted)" fontSize={12} />
              <Tooltip
                formatter={(value: number) => formatCurrency(value)}
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                }}
              />
              <Line
                type="monotone"
                dataKey="cost"
                name="Cost"
                stroke="var(--accent)"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {costByModelQuery.data && costByModelQuery.data.length > 0 && (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Model</th>
                <th>Requests</th>
                <th>Tokens</th>
                <th>Total Cost</th>
              </tr>
            </thead>
            <tbody>
              {costByModelQuery.data.map((row) => (
                <tr key={row.model}>
                  <td className="cell-strong">{row.model}</td>
                  <td>{formatCount(row.total_requests)}</td>
                  <td>{formatCount(row.total_tokens)}</td>
                  <td>{formatCurrency(parseDecimal(row.total_cost))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
