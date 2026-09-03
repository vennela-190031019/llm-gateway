import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as requestsApi from "../api/requests";
import { makeRequest } from "../test/factories";
import { Requests } from "./Requests";

vi.mock("../api/requests");

function renderRequestsPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/requests"]}>
        <Routes>
          <Route path="/requests" element={<Requests />} />
          <Route path="/requests/:requestId" element={<div>Request Detail Page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Requests", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders one row per request with model, provider, and status", async () => {
    vi.mocked(requestsApi.listRequests).mockResolvedValue([
      makeRequest({ model: "gpt-4o-mini", provider: "openai", status: "success" }),
      makeRequest({
        request_id: "44444444-4444-4444-4444-444444444444",
        model: "llama3.1",
        provider: "ollama",
        status: "error",
      }),
    ]);

    renderRequestsPage();

    expect(await screen.findByText("gpt-4o-mini")).toBeInTheDocument();
    expect(screen.getByText("llama3.1")).toBeInTheDocument();
    expect(screen.getByText("openai")).toBeInTheDocument();
    expect(screen.getByText("ollama")).toBeInTheDocument();
    expect(screen.getByText("success")).toBeInTheDocument();
    expect(screen.getByText("error")).toBeInTheDocument();
  });

  it("navigates to the request detail page when a row is clicked", async () => {
    const user = userEvent.setup();
    vi.mocked(requestsApi.listRequests).mockResolvedValue([makeRequest({ model: "gpt-4o-mini" })]);

    renderRequestsPage();

    const modelCell = await screen.findByText("gpt-4o-mini");
    const row = modelCell.closest("tr");
    if (!row) throw new Error("Row not found");
    await user.click(row);

    expect(await screen.findByText("Request Detail Page")).toBeInTheDocument();
  });

  it("shows an error notice when GET /requests fails", async () => {
    vi.mocked(requestsApi.listRequests).mockRejectedValue(new Error("Network Error"));

    renderRequestsPage();

    expect(await screen.findByText(/Failed to load data/i)).toBeInTheDocument();
  });
});
