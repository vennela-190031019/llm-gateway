import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as requestsApi from "../api/requests";
import { makeRequest } from "../test/factories";
import { Costs } from "./Costs";

vi.mock("../api/requests");

function renderCosts() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Costs />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function statCardValue(label: string): string {
  // Scoped to .stat-grid: "Total Cost" also appears as a table column
  // header on this page, which a page-wide getByText would collide with.
  const statGrid = document.querySelector(".stat-grid");
  if (!statGrid) throw new Error("Could not find .stat-grid");
  const card = within(statGrid as HTMLElement).getByText(label).closest(".stat-card");
  if (!card) throw new Error(`Could not find stat card for "${label}"`);
  return within(card as HTMLElement).getByText(/.+/, { selector: ".stat-card-value" })
    .textContent as string;
}

describe("Costs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders without crashing and shows the total cost from the summary endpoint", async () => {
    vi.mocked(requestsApi.getRequestsSummary).mockResolvedValue({
      total_requests: 4,
      success_rate: 75,
      average_latency_ms: 300,
      total_tokens: 200,
      total_cost: "0.08",
      cache_hit_rate: 25,
    });
    vi.mocked(requestsApi.getCostByModel).mockResolvedValue([
      { model: "gpt-4o-mini", total_requests: 3, total_tokens: 150, total_cost: "0.03" },
      { model: "gpt-4o", total_requests: 1, total_tokens: 50, total_cost: "0.05" },
    ]);
    vi.mocked(requestsApi.listRequests).mockResolvedValue([makeRequest()]);

    renderCosts();

    await waitFor(() => expect(statCardValue("Total Cost")).toBe("$0.08"));
    expect(statCardValue("Total Requests")).toBe("4");

    expect(await screen.findByText("gpt-4o-mini")).toBeInTheDocument();
    expect(screen.getByText("gpt-4o")).toBeInTheDocument();
  });

  it("shows an error notice when the cost-by-model request fails", async () => {
    vi.mocked(requestsApi.getRequestsSummary).mockResolvedValue({
      total_requests: 0,
      success_rate: null,
      average_latency_ms: null,
      total_tokens: 0,
      total_cost: "0",
      cache_hit_rate: null,
    });
    vi.mocked(requestsApi.getCostByModel).mockRejectedValue(new Error("Network Error"));
    vi.mocked(requestsApi.listRequests).mockResolvedValue([]);

    renderCosts();

    expect(await screen.findByText(/Failed to load data/i)).toBeInTheDocument();
  });
});
