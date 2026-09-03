import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addEvaluationCase,
  createEvaluationDataset,
  getEvaluationDataset,
  getEvaluationRun,
  listEvaluationDatasets,
  listEvaluationRunResults,
  startEvaluationRun,
} from "../api/evaluations";
import type { EvaluationCaseRead, EvaluationRunStatus, EvaluationRunSummary } from "../api/types";
import { ErrorNotice } from "../components/ErrorNotice";
import { Modal } from "../components/Modal";
import { StatCard } from "../components/StatCard";
import {
  formatCount,
  formatCurrency,
  formatDateTime,
  formatLatency,
  parseDecimal,
} from "../utils/format";

// No backend endpoint lists registered evaluator/metric names — this
// mirrors backend/app/services/evaluators/registry.py's two entries.
const KNOWN_METRICS = ["exact_match", "answer_relevance"] as const;

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function statusPillClass(status: EvaluationRunStatus): string {
  if (status === "completed") return "pill-success";
  if (status === "failed") return "pill-error";
  return "pill-info";
}

export function Evaluations() {
  const queryClient = useQueryClient();
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [isCreateModalOpen, setCreateModalOpen] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [recentRuns, setRecentRuns] = useState<EvaluationRunSummary[]>([]);

  const datasetsQuery = useQuery({
    queryKey: ["evaluations", "datasets"],
    queryFn: () => listEvaluationDatasets(),
  });
  const datasetDetailQuery = useQuery({
    queryKey: ["evaluations", "datasets", selectedDatasetId],
    queryFn: () => getEvaluationDataset(selectedDatasetId as string),
    enabled: selectedDatasetId !== null,
  });

  const createDatasetMutation = useMutation({
    mutationFn: createEvaluationDataset,
    onSuccess: (dataset) => {
      queryClient.invalidateQueries({ queryKey: ["evaluations", "datasets"] });
      selectDataset(dataset.id);
      setCreateModalOpen(false);
      createDatasetMutation.reset();
    },
  });

  function selectDataset(datasetId: string) {
    setSelectedDatasetId(datasetId);
    setSelectedRunId(null);
    setRecentRuns([]);
  }

  function refetchDatasetDetail() {
    queryClient.invalidateQueries({ queryKey: ["evaluations", "datasets", selectedDatasetId] });
  }

  function handleRunStarted(run: EvaluationRunSummary) {
    setRecentRuns((prev) => [run, ...prev]);
    setSelectedRunId(run.id);
  }

  return (
    <div className="page">
      <div className="page-header page-header-row">
        <div>
          <h1>Evaluations</h1>
          <p className="text-muted">
            Build datasets, run them against a model, and inspect scored results.
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setCreateModalOpen(true)}>
          New Dataset
        </button>
      </div>

      {datasetsQuery.isError && <ErrorNotice message={errorMessage(datasetsQuery.error)} />}

      <div className="split-layout">
        <div className="list-panel">
          <div className="list-panel-header">
            <h2>Datasets</h2>
          </div>
          {datasetsQuery.isLoading && <div className="page-loading">Loading…</div>}
          {datasetsQuery.data && datasetsQuery.data.length === 0 && (
            <div className="empty-state empty-state-inline">
              <p>No datasets yet.</p>
            </div>
          )}
          <div className="list-items">
            {datasetsQuery.data?.map((dataset) => (
              <button
                key={dataset.id}
                type="button"
                className={
                  "list-item" + (dataset.id === selectedDatasetId ? " list-item-active" : "")
                }
                onClick={() => selectDataset(dataset.id)}
              >
                <div className="list-item-title">{dataset.name}</div>
                {dataset.description && (
                  <div className="list-item-subtitle">{dataset.description}</div>
                )}
              </button>
            ))}
          </div>
        </div>

        <div className="detail-panel">
          {!selectedDatasetId && (
            <div className="empty-state">
              <p>Select a dataset to view cases and start a run, or create a new one.</p>
            </div>
          )}
          {selectedDatasetId && datasetDetailQuery.isLoading && (
            <div className="page-loading">Loading dataset…</div>
          )}
          {selectedDatasetId && datasetDetailQuery.isError && (
            <ErrorNotice message={errorMessage(datasetDetailQuery.error)} />
          )}
          {datasetDetailQuery.data && (
            <>
              <div className="panel">
                <h2>{datasetDetailQuery.data.name}</h2>
                {datasetDetailQuery.data.description && (
                  <p className="text-muted">{datasetDetailQuery.data.description}</p>
                )}
              </div>
              <div className="panel">
                <div className="section-title">Cases ({datasetDetailQuery.data.cases.length})</div>
                <CaseList cases={datasetDetailQuery.data.cases} />
                <NewCaseForm
                  datasetId={datasetDetailQuery.data.id}
                  onCreated={refetchDatasetDetail}
                />
              </div>
              <div className="panel">
                <StartRunForm
                  datasetId={datasetDetailQuery.data.id}
                  onStarted={handleRunStarted}
                />
              </div>
              {recentRuns.length > 0 && (
                <div className="panel">
                  <div className="section-title">Runs (this session)</div>
                  <RunList
                    runs={recentRuns}
                    selectedRunId={selectedRunId}
                    onSelect={setSelectedRunId}
                  />
                </div>
              )}
              {selectedRunId && (
                <div className="panel">
                  <RunResults runId={selectedRunId} />
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {isCreateModalOpen && (
        <Modal
          title="New Evaluation Dataset"
          onClose={() => {
            setCreateModalOpen(false);
            createDatasetMutation.reset();
          }}
        >
          <NewDatasetForm
            onSubmit={(input) => createDatasetMutation.mutate(input)}
            isSubmitting={createDatasetMutation.isPending}
            error={
              createDatasetMutation.isError ? errorMessage(createDatasetMutation.error) : null
            }
          />
        </Modal>
      )}
    </div>
  );
}

function NewDatasetForm({
  onSubmit,
  isSubmitting,
  error,
}: {
  onSubmit: (input: { name: string; description?: string }) => void;
  isSubmitting: boolean;
  error: string | null;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit({ name, description: description.trim() ? description : undefined });
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <label className="field">
        <span>Name</span>
        <input
          type="text"
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="geography-qa"
        />
      </label>
      <label className="field">
        <span>Description (optional)</span>
        <input
          type="text"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </label>
      {error && <ErrorNotice message={error} />}
      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
          {isSubmitting ? "Creating…" : "Create"}
        </button>
      </div>
    </form>
  );
}

function CaseList({ cases }: { cases: EvaluationCaseRead[] }) {
  if (cases.length === 0) {
    return <p className="text-muted">No cases yet — add one below.</p>;
  }

  return (
    <div className="table-wrapper">
      <table className="data-table">
        <thead>
          <tr>
            <th>Input</th>
            <th>Expected Output</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((evaluationCase) => (
            <tr key={evaluationCase.id}>
              <td>{evaluationCase.input}</td>
              <td>{evaluationCase.expected_output ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NewCaseForm({ datasetId, onCreated }: { datasetId: string; onCreated: () => void }) {
  const [input, setInput] = useState("");
  const [expectedOutput, setExpectedOutput] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      addEvaluationCase(datasetId, {
        input,
        expected_output: expectedOutput.trim() ? expectedOutput : undefined,
      }),
    onSuccess: () => {
      setInput("");
      setExpectedOutput("");
      onCreated();
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <div className="section-title">Add Case</div>
      <label className="field">
        <span>Input</span>
        <textarea
          required
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="What is the capital of France?"
        />
      </label>
      <label className="field">
        <span>Expected output (optional)</span>
        <input
          type="text"
          value={expectedOutput}
          onChange={(event) => setExpectedOutput(event.target.value)}
          placeholder="Paris"
        />
      </label>
      {mutation.isError && <ErrorNotice message={errorMessage(mutation.error)} />}
      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={mutation.isPending}>
          {mutation.isPending ? "Adding…" : "Add Case"}
        </button>
      </div>
    </form>
  );
}

function StartRunForm({
  datasetId,
  onStarted,
}: {
  datasetId: string;
  onStarted: (run: EvaluationRunSummary) => void;
}) {
  const [model, setModel] = useState("gpt-4o-mini");
  const [provider, setProvider] = useState("openai");
  const [metrics, setMetrics] = useState<string[]>(["exact_match"]);

  const mutation = useMutation({
    mutationFn: () => startEvaluationRun({ dataset_id: datasetId, model, provider, metrics }),
    onSuccess: onStarted,
  });

  function toggleMetric(metric: string) {
    setMetrics((prev) =>
      prev.includes(metric) ? prev.filter((value) => value !== metric) : [...prev, metric],
    );
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <div className="section-title">Start Run</div>
      <div className="form-row">
        <label className="field">
          <span>Model</span>
          <input
            type="text"
            required
            value={model}
            onChange={(event) => setModel(event.target.value)}
          />
        </label>
        <label className="field">
          <span>Provider</span>
          <input
            type="text"
            required
            value={provider}
            onChange={(event) => setProvider(event.target.value)}
          />
        </label>
      </div>
      <div className="field">
        <span>Metrics</span>
        <div className="checkbox-group">
          {KNOWN_METRICS.map((metric) => (
            <label className="checkbox-row" key={metric}>
              <input
                type="checkbox"
                checked={metrics.includes(metric)}
                onChange={() => toggleMetric(metric)}
              />
              {metric}
            </label>
          ))}
        </div>
      </div>
      {mutation.isError && <ErrorNotice message={errorMessage(mutation.error)} />}
      <div className="form-actions">
        <button
          type="submit"
          className="btn btn-primary"
          disabled={mutation.isPending || metrics.length === 0}
        >
          {mutation.isPending ? "Running…" : "Start Run"}
        </button>
      </div>
    </form>
  );
}

function RunList({
  runs,
  selectedRunId,
  onSelect,
}: {
  runs: EvaluationRunSummary[];
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
}) {
  return (
    <div className="table-wrapper">
      <table className="data-table data-table-clickable">
        <thead>
          <tr>
            <th>Run</th>
            <th>Model</th>
            <th>Provider</th>
            <th>Status</th>
            <th>Cases</th>
            <th>Started</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr
              key={run.id}
              className={run.id === selectedRunId ? "row-selected" : undefined}
              onClick={() => onSelect(run.id)}
            >
              <td className="cell-mono">{run.id.slice(0, 8)}</td>
              <td>{run.model}</td>
              <td>{run.provider}</td>
              <td>
                <span className={"pill " + statusPillClass(run.status)}>{run.status}</span>
              </td>
              <td>{run.case_count}</td>
              <td>{formatDateTime(run.started_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RunResults({ runId }: { runId: string }) {
  const summaryQuery = useQuery({
    queryKey: ["evaluations", "runs", runId],
    queryFn: () => getEvaluationRun(runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "running" || status === "pending" ? 2000 : false;
    },
  });
  const resultsQuery = useQuery({
    queryKey: ["evaluations", "runs", runId, "results"],
    queryFn: () => listEvaluationRunResults(runId),
  });

  return (
    <div>
      <div className="section-title">Run Results</div>
      {summaryQuery.isError && <ErrorNotice message={errorMessage(summaryQuery.error)} />}
      {summaryQuery.data && (
        <div className="stat-grid">
          <StatCard label="Status" value={summaryQuery.data.status} />
          <StatCard label="Cases" value={formatCount(summaryQuery.data.case_count)} />
          {Object.entries(summaryQuery.data.average_scores).map(([metric, score]) => (
            <StatCard key={metric} label={metric} value={score.toFixed(2)} />
          ))}
        </div>
      )}

      {resultsQuery.isError && <ErrorNotice message={errorMessage(resultsQuery.error)} />}
      {resultsQuery.data && resultsQuery.data.length === 0 && (
        <p className="text-muted">No per-case results yet.</p>
      )}
      {resultsQuery.data && resultsQuery.data.length > 0 && (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Output</th>
                <th>Latency</th>
                <th>Tokens</th>
                <th>Cost</th>
                <th>Scores</th>
              </tr>
            </thead>
            <tbody>
              {resultsQuery.data.map((result) => (
                <tr key={result.id}>
                  <td>{result.actual_output}</td>
                  <td>{formatLatency(result.latency_ms)}</td>
                  <td>{formatCount(result.tokens)}</td>
                  <td>{formatCurrency(parseDecimal(result.cost))}</td>
                  <td>
                    <div className="chip-row">
                      {Object.entries(result.scores).map(([metric, score]) => (
                        <span key={metric} className="chip">
                          {metric}: {score.toFixed(2)}
                        </span>
                      ))}
                    </div>
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
