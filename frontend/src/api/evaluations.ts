import { apiClient } from "./client";
import type {
  EvaluationCaseRead,
  EvaluationDatasetDetailRead,
  EvaluationDatasetRead,
  EvaluationResultRead,
  EvaluationRunSummary,
} from "./types";

export async function listEvaluationDatasets(): Promise<EvaluationDatasetRead[]> {
  const response = await apiClient.get<EvaluationDatasetRead[]>("/evaluations/datasets");
  return response.data;
}

export async function getEvaluationDataset(
  datasetId: string,
): Promise<EvaluationDatasetDetailRead> {
  const response = await apiClient.get<EvaluationDatasetDetailRead>(
    `/evaluations/datasets/${datasetId}`,
  );
  return response.data;
}

export interface CreateEvaluationDatasetInput {
  name: string;
  description?: string | null;
}

export async function createEvaluationDataset(
  input: CreateEvaluationDatasetInput,
): Promise<EvaluationDatasetRead> {
  const response = await apiClient.post<EvaluationDatasetRead>("/evaluations/datasets", input);
  return response.data;
}

export interface AddEvaluationCaseInput {
  input: string;
  expected_output?: string | null;
}

export async function addEvaluationCase(
  datasetId: string,
  input: AddEvaluationCaseInput,
): Promise<EvaluationCaseRead> {
  const response = await apiClient.post<EvaluationCaseRead>(
    `/evaluations/datasets/${datasetId}/cases`,
    input,
  );
  return response.data;
}

export interface StartEvaluationRunInput {
  dataset_id: string;
  model: string;
  provider: string;
  metrics: string[];
}

export async function startEvaluationRun(
  input: StartEvaluationRunInput,
): Promise<EvaluationRunSummary> {
  const response = await apiClient.post<EvaluationRunSummary>("/evaluations/runs", input);
  return response.data;
}

export async function getEvaluationRun(runId: string): Promise<EvaluationRunSummary> {
  const response = await apiClient.get<EvaluationRunSummary>(`/evaluations/runs/${runId}`);
  return response.data;
}

export async function listEvaluationRunResults(runId: string): Promise<EvaluationResultRead[]> {
  const response = await apiClient.get<EvaluationResultRead[]>(
    `/evaluations/runs/${runId}/results`,
  );
  return response.data;
}
