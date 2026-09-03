import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { listRequests } from "../api/requests";
import { ErrorNotice } from "../components/ErrorNotice";
import {
  formatCount,
  formatCurrency,
  formatDateTime,
  formatLatency,
  parseDecimal,
  truncateId,
} from "../utils/format";

export function Requests() {
  const navigate = useNavigate();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["requests", { limit: 100 }],
    queryFn: () => listRequests(100),
  });

  return (
    <div className="page">
      <div className="page-header">
        <h1>Requests</h1>
        <p className="text-muted">Most recent LLM requests, from GET /requests.</p>
      </div>

      {isError && (
        <ErrorNotice message={error instanceof Error ? error.message : "Couldn't reach the server."} />
      )}

      {isLoading && !isError && <div className="page-loading">Loading requests…</div>}

      {data && data.length === 0 && (
        <div className="empty-state">
          <p>No requests recorded yet.</p>
        </div>
      )}

      {data && data.length > 0 && (
        <div className="table-wrapper">
          <table className="data-table data-table-clickable">
            <thead>
              <tr>
                <th>Request ID</th>
                <th>Model</th>
                <th>Provider</th>
                <th>Latency</th>
                <th>Tokens</th>
                <th>Cost</th>
                <th>Status</th>
                <th>Cache</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {data.map((request) => (
                <tr
                  key={request.request_id}
                  onClick={() => navigate(`/requests/${request.request_id}`)}
                >
                  <td className="cell-mono">{truncateId(request.request_id)}</td>
                  <td className="cell-strong">{request.model}</td>
                  <td>{request.provider ?? "—"}</td>
                  <td>{formatLatency(request.latency_ms)}</td>
                  <td>{formatCount(request.total_tokens)}</td>
                  <td>{formatCurrency(parseDecimal(request.estimated_cost))}</td>
                  <td>
                    <span
                      className={
                        "pill " + (request.status === "success" ? "pill-success" : "pill-error")
                      }
                    >
                      {request.status}
                    </span>
                  </td>
                  <td>{request.cache_hit ? "Hit" : "Miss"}</td>
                  <td>{formatDateTime(request.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
