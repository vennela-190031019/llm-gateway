import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as evaluationsApi from "../api/evaluations";
import type {
  EvaluationDatasetDetailRead,
  EvaluationDatasetRead,
  EvaluationRunSummary,
} from "../api/types";
import { Evaluations } from "./Evaluations";

vi.mock("../api/evaluations");

function renderEvaluations() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Evaluations />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const dataset: EvaluationDatasetRead = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "geography-qa",
  description: "Capital cities",
  owner_id: "u1",
  created_at: "2026-01-01T00:00:00Z",
};

const datasetDetail: EvaluationDatasetDetailRead = {
  ...dataset,
  cases: [
    {
      id: "22222222-2222-2222-2222-222222222222",
      dataset_id: dataset.id,
      input: "What is the capital of France?",
      expected_output: "Paris",
      created_at: "2026-01-01T00:00:00Z",
    },
  ],
};

const runSummary: EvaluationRunSummary = {
  id: "33333333-3333-3333-3333-333333333333",
  dataset_id: dataset.id,
  model: "gpt-4o-mini",
  provider: "openai",
  status: "completed",
  started_at: "2026-01-01T00:00:00Z",
  completed_at: "2026-01-01T00:00:01Z",
  case_count: 1,
  average_scores: { exact_match: 1 },
};

describe("Evaluations", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the dataset list without crashing", async () => {
    vi.mocked(evaluationsApi.listEvaluationDatasets).mockResolvedValue([dataset]);

    renderEvaluations();

    expect(await screen.findByText("geography-qa")).toBeInTheDocument();
    expect(screen.getByText("Capital cities")).toBeInTheDocument();
  });

  it("shows a dataset's cases when selected", async () => {
    vi.mocked(evaluationsApi.listEvaluationDatasets).mockResolvedValue([dataset]);
    vi.mocked(evaluationsApi.getEvaluationDataset).mockResolvedValue(datasetDetail);
    const user = userEvent.setup();

    renderEvaluations();

    await user.click(await screen.findByText("geography-qa"));

    expect(await screen.findByText("What is the capital of France?")).toBeInTheDocument();
    expect(screen.getByText("Paris")).toBeInTheDocument();
  });

  it("starting a run calls the API with the selected model, provider, and metrics", async () => {
    vi.mocked(evaluationsApi.listEvaluationDatasets).mockResolvedValue([dataset]);
    vi.mocked(evaluationsApi.getEvaluationDataset).mockResolvedValue(datasetDetail);
    vi.mocked(evaluationsApi.startEvaluationRun).mockResolvedValue(runSummary);
    vi.mocked(evaluationsApi.getEvaluationRun).mockResolvedValue(runSummary);
    vi.mocked(evaluationsApi.listEvaluationRunResults).mockResolvedValue([]);
    const user = userEvent.setup();

    renderEvaluations();

    await user.click(await screen.findByText("geography-qa"));
    await screen.findByText("What is the capital of France?");
    await user.click(screen.getByRole("button", { name: "Start Run" }));

    // react-query v5 calls mutationFn with a second (internal context)
    // argument — assert on the payload we actually care about.
    expect(vi.mocked(evaluationsApi.startEvaluationRun).mock.calls[0]?.[0]).toEqual({
      dataset_id: dataset.id,
      model: "gpt-4o-mini",
      provider: "openai",
      metrics: ["exact_match"],
    });
    expect(await screen.findByText("Run Results")).toBeInTheDocument();
  });
});
