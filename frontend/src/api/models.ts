import { apiClient } from "./client";
import type { ModelRead } from "./types";

export async function listModels(): Promise<ModelRead[]> {
  const response = await apiClient.get<ModelRead[]>("/models");
  return response.data;
}
