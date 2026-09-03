import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as healthApi from "../api/health";
import { SystemHealth } from "./SystemHealth";

vi.mock("../api/health");

const SAMPLE_METRICS_TEXT = `
# HELP llm_requests_total Total number of LLM requests processed
# TYPE llm_requests_total counter
llm_requests_total{model="gpt-4o-mini",provider="openai",status="success"} 3.0
llm_requests_total_created{model="gpt-4o-mini",provider="openai",status="success"} 1788200000.0
# HELP llm_errors_total Total number of LLM request errors
# TYPE llm_errors_total counter
llm_errors_total{model="gpt-4o",provider="openai",error_type="ProviderTimeoutError"} 2.0
# HELP llm_cache_hits_total Total number of cache hits
# TYPE llm_cache_hits_total counter
llm_cache_hits_total 5.0
# HELP llm_cache_misses_total Total number of cache misses
# TYPE llm_cache_misses_total counter
llm_cache_misses_total 7.0
# HELP http_requests_total Total number of HTTP requests processed
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/api/v1/healthz",status_code="200"} 10.0
`;

function renderSystemHealth() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SystemHealth />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function statCardValue(label: string): string {
  const card = screen.getByText(label).closest(".stat-card");
  if (!card) throw new Error(`Could not find stat card for "${label}"`);
  return within(card as HTMLElement).getByText(/.+/, { selector: ".stat-card-value" })
    .textContent as string;
}

describe("SystemHealth", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders without crashing and shows a healthy status", async () => {
    vi.mocked(healthApi.getHealth).mockResolvedValue({ status: "ok" });
    vi.mocked(healthApi.getRawMetricsText).mockResolvedValue(SAMPLE_METRICS_TEXT);

    renderSystemHealth();

    expect(await screen.findByText("Backend is healthy")).toBeInTheDocument();
  });

  it("parses and displays the key metrics from the raw Prometheus text", async () => {
    vi.mocked(healthApi.getHealth).mockResolvedValue({ status: "ok" });
    vi.mocked(healthApi.getRawMetricsText).mockResolvedValue(SAMPLE_METRICS_TEXT);

    renderSystemHealth();

    await waitFor(() => expect(statCardValue("Total LLM Requests")).toBe("3"));
    expect(statCardValue("Total LLM Errors")).toBe("2");
    expect(statCardValue("Cache Hits")).toBe("5");
    expect(statCardValue("Cache Misses")).toBe("7");
    expect(statCardValue("Total HTTP Requests")).toBe("10");
  });

  it("shows an error notice when the health check fails", async () => {
    vi.mocked(healthApi.getHealth).mockRejectedValue(new Error("Network Error"));
    vi.mocked(healthApi.getRawMetricsText).mockResolvedValue(SAMPLE_METRICS_TEXT);

    renderSystemHealth();

    expect(await screen.findByText(/Failed to load data/i)).toBeInTheDocument();
  });
});
