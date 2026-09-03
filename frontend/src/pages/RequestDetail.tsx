import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { getRequest } from "../api/requests";
import { ErrorNotice } from "../components/ErrorNotice";
import { formatCount, formatCurrency, formatDateTime, formatLatency, parseDecimal } from "../utils/format";

export function RequestDetail() {
  const { requestId } = useParams<{ requestId: string }>();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["requests", requestId],
    queryFn: () => getRequest(requestId as string),
    enabled: Boolean(requestId),
  });

  return (
    <div className="page">
      <div className="page-header">
        <Link to="/requests" className="back-link">
          ← Back to Requests
        </Link>
        <h1>Request Detail</h1>
      </div>

      {isError && (
        <ErrorNotice message={error instanceof Error ? error.message : "Couldn't reach the server."} />
      )}

      {isLoading && !isError && <div className="page-loading">Loading request…</div>}

      {data && (
        <div className="detail-card">
          <dl className="detail-grid">
            <div>
              <dt>Request ID</dt>
              <dd className="cell-mono">{data.request_id}</dd>
            </div>
            <div>
              <dt>Trace ID</dt>
              <dd className="cell-mono">{data.trace_id}</dd>
            </div>
            <div>
              <dt>Model</dt>
              <dd>{data.model}</dd>
            </div>
            <div>
              <dt>Provider</dt>
              <dd>{data.provider ?? "—"}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>
                <span
                  className={"pill " + (data.status === "success" ? "pill-success" : "pill-error")}
                >
                  {data.status}
                </span>
              </dd>
            </div>
            <div>
              <dt>Cache</dt>
              <dd>{data.cache_hit ? "Hit" : "Miss"}</dd>
            </div>
            <div>
              <dt>Latency</dt>
              <dd>{formatLatency(data.latency_ms)}</dd>
            </div>
            <div>
              <dt>Input tokens</dt>
              <dd>{formatCount(data.input_tokens)}</dd>
            </div>
            <div>
              <dt>Output tokens</dt>
              <dd>{formatCount(data.output_tokens)}</dd>
            </div>
            <div>
              <dt>Total tokens</dt>
              <dd>{formatCount(data.total_tokens)}</dd>
            </div>
            <div>
              <dt>Estimated cost</dt>
              <dd>{formatCurrency(parseDecimal(data.estimated_cost))}</dd>
            </div>
            <div>
              <dt>Timestamp</dt>
              <dd>{formatDateTime(data.created_at)}</dd>
            </div>
          </dl>
          {data.error && (
            <div className="notice notice-error detail-error">
              <strong>Error:</strong> {data.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
