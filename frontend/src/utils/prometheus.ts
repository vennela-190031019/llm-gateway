// Minimal parser for the Prometheus text exposition format (what
// GET /metrics returns) — no library needed for the handful of counters
// this app cares about. Each matching sample line looks like:
//
//   llm_requests_total{model="gpt-4o-mini",provider="openai",status="success"} 3.0
//
// Deliberately anchors on the metric name followed by an optional
// `{...}` label set, then whitespace, then the value, end of line — so
// e.g. "llm_requests_total" doesn't also match
// "llm_requests_total_created" (the `_created` companion samples
// prometheus_client emits for every Counter).

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Sums every sample's value for a given counter/gauge name, across all label combinations. */
export function sumMetric(text: string, metricName: string): number {
  const pattern = new RegExp(
    `^${escapeRegExp(metricName)}(?:\\{[^}]*\\})?\\s+([0-9eE.+-]+)$`,
    "gm",
  );
  let total = 0;
  for (const match of text.matchAll(pattern)) {
    const value = Number.parseFloat(match[1]);
    if (!Number.isNaN(value)) {
      total += value;
    }
  }
  return total;
}

export interface MetricsSummary {
  totalLlmRequests: number;
  totalLlmErrors: number;
  cacheHits: number;
  cacheMisses: number;
  totalHttpRequests: number;
}

export function summarizeMetrics(text: string): MetricsSummary {
  return {
    totalLlmRequests: sumMetric(text, "llm_requests_total"),
    totalLlmErrors: sumMetric(text, "llm_errors_total"),
    cacheHits: sumMetric(text, "llm_cache_hits_total"),
    cacheMisses: sumMetric(text, "llm_cache_misses_total"),
    totalHttpRequests: sumMetric(text, "http_requests_total"),
  };
}
