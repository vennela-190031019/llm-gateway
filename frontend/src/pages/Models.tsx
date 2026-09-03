import { useQuery } from "@tanstack/react-query";
import { listModels } from "../api/models";
import { formatCurrency, parseDecimal } from "../utils/format";

export function Models() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["models"],
    queryFn: () => listModels(),
  });

  return (
    <div className="page">
      <div className="page-header">
        <h1>Models</h1>
        <p className="text-muted">Active models in the catalog, from GET /models.</p>
      </div>

      {isLoading && <div className="page-loading">Loading models…</div>}

      {isError && (
        <div className="notice notice-error">
          Failed to load models{error instanceof Error ? `: ${error.message}` : "."}
        </div>
      )}

      {data && data.length === 0 && (
        <div className="empty-state">
          <p>No active models in the catalog yet.</p>
        </div>
      )}

      {data && data.length > 0 && (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Provider</th>
                <th>Tier</th>
                <th>Input $ / 1k tokens</th>
                <th>Output $ / 1k tokens</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.map((model) => (
                <tr key={model.id}>
                  <td className="cell-strong">{model.name}</td>
                  <td>{model.provider_name}</td>
                  <td>
                    <span className="pill">{model.tier}</span>
                  </td>
                  <td>{formatCurrency(parseDecimal(model.input_price_per_1k))}</td>
                  <td>{formatCurrency(parseDecimal(model.output_price_per_1k))}</td>
                  <td>
                    <span className={"pill " + (model.is_active ? "pill-success" : "pill-muted")}>
                      {model.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
