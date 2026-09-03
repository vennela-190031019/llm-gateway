import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as requestsApi from "../api/requests";
import type { RequestsSummaryRead } from "../api/types";
import { makeRequest } from "../test/factories";
import { Dashboard } from "./Dashboard";

vi.mock("../api/requests");

function renderDashboard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function makeSummary(overrides: Partial<RequestsSummaryRead> = {}): RequestsSummaryRead {
  return {
    total_requests: 2,
    success_rate: 50,
    average_latency_ms: 500,
    total_tokens: 150,
    total_cost: "0.01",
    cache_hit_rate: 50,
    ...overrides,
  };
}

function statCardValue(label: string): string {
  const card = screen.getByText(label).closest(".stat-card");
  if (!card) throw new Error(`Could not find stat card for "${label}"`);
  return within(card as HTMLElement).getByText(/.+/, { selector: ".stat-card-value" })
    .textContent as string;
}

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the six summary cards from GET /requests/summary", async () => {
    vi.mocked(requestsApi.getRequestsSummary).mockResolvedValue(makeSummary());
    vi.mocked(requestsApi.listRequests).mockResolvedValue([makeRequest()]);

    renderDashboard();

    await waitFor(() => expect(statCardValue("Total Requests")).toBe("2"));
    expect(statCardValue("Success Rate")).toBe("50.0%");
    expect(statCardValue("Cache Hit Rate")).toBe("50.0%");
    expect(statCardValue("Total Tokens")).toBe("150");
    expect(statCardValue("Estimated Cost")).toBe("$0.01");
  });

  it("renders dashes for rates when there are no requests yet", async () => {
    vi.mocked(requestsApi.getRequestsSummary).mockResolvedValue(
      makeSummary({
        total_requests: 0,
        success_rate: null,
        average_latency_ms: null,
        total_tokens: 0,
        total_cost: "0",
        cache_hit_rate: null,
      }),
    );
    vi.mocked(requestsApi.listRequests).mockResolvedValue([]);

    renderDashboard();

    await waitFor(() => expect(statCardValue("Total Requests")).toBe("0"));
    expect(statCardValue("Success Rate")).toBe("—");
    expect(statCardValue("Average Latency")).toBe("—");
    expect(statCardValue("Cache Hit Rate")).toBe("—");
  });

  it("shows an error notice when the summary request fails", async () => {
    vi.mocked(requestsApi.getRequestsSummary).mockRejectedValue(new Error("Network Error"));
    vi.mocked(requestsApi.listRequests).mockResolvedValue([]);

    renderDashboard();

    expect(await screen.findByText(/Failed to load data/i)).toBeInTheDocument();
  });
});
