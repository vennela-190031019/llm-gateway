import { apiClient } from "./client";
import type { LLMRequestRead, ModelCostRead, RequestsSummaryRead } from "./types";

export async function listRequests(limit = 100): Promise<LLMRequestRead[]> {
  const response = await apiClient.get<LLMRequestRead[]>("/requests", {
    params: { limit },
  });
  return response.data;
}

export async function getRequest(requestId: string): Promise<LLMRequestRead> {
  const response = await apiClient.get<LLMRequestRead>(`/requests/${requestId}`);
  return response.data;
}

export async function getRequestsSummary(): Promise<RequestsSummaryRead> {
  const response = await apiClient.get<RequestsSummaryRead>("/requests/summary");
  return response.data;
}

export async function getCostByModel(): Promise<ModelCostRead[]> {
  const response = await apiClient.get<ModelCostRead[]>("/requests/cost-by-model");
  return response.data;
}
