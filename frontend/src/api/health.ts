import axios from "axios";
import { API_ROOT_URL, apiClient } from "./client";

export interface HealthRead {
  status: string;
}

export async function getHealth(): Promise<HealthRead> {
  const response = await apiClient.get<HealthRead>("/healthz");
  return response.data;
}

/**
 * Raw Prometheus text exposition format from GET /metrics (root-mounted,
 * not under /api/v1 — see API_ROOT_URL). Uses a bare axios call instead
 * of `apiClient`: this endpoint isn't behind auth, and isn't JSON, so
 * neither the Bearer-token interceptor nor axios's default JSON parsing
 * apply here.
 */
export async function getRawMetricsText(): Promise<string> {
  const response = await axios.get<string>(`${API_ROOT_URL}/metrics`, {
    responseType: "text",
    transformResponse: (data: string) => data,
  });
  return response.data;
}
