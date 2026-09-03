import { apiClient } from "./client";
import type {
  PromptRenderResponse,
  PromptTemplateDetailRead,
  PromptTemplateRead,
  PromptVersionRead,
} from "./types";

export async function listPromptTemplates(): Promise<PromptTemplateRead[]> {
  const response = await apiClient.get<PromptTemplateRead[]>("/prompts");
  return response.data;
}

export async function getPromptTemplate(name: string): Promise<PromptTemplateDetailRead> {
  const response = await apiClient.get<PromptTemplateDetailRead>(
    `/prompts/${encodeURIComponent(name)}`,
  );
  return response.data;
}

export interface CreatePromptTemplateInput {
  name: string;
  description?: string | null;
}

export async function createPromptTemplate(
  input: CreatePromptTemplateInput,
): Promise<PromptTemplateRead> {
  const response = await apiClient.post<PromptTemplateRead>("/prompts", input);
  return response.data;
}

export interface CreatePromptVersionInput {
  template_text: string;
  variables: string[];
  model: string;
  temperature: number;
}

export async function createPromptVersion(
  name: string,
  input: CreatePromptVersionInput,
): Promise<PromptVersionRead> {
  const response = await apiClient.post<PromptVersionRead>(
    `/prompts/${encodeURIComponent(name)}/versions`,
    input,
  );
  return response.data;
}

/**
 * GET /prompts/{name}/render accepts variables as query params (or a
 * JSON body via FastAPI's Body-on-GET support — query params are the
 * simpler, more broadly-compatible choice from a plain HTTP client).
 */
export async function renderPromptTemplate(
  name: string,
  variables: Record<string, string>,
  version?: number,
): Promise<PromptRenderResponse> {
  const params: Record<string, string> = { ...variables };
  if (version !== undefined) {
    params.version = String(version);
  }
  const response = await apiClient.get<PromptRenderResponse>(
    `/prompts/${encodeURIComponent(name)}/render`,
    { params },
  );
  return response.data;
}

export async function activatePromptVersion(
  name: string,
  version: number,
): Promise<PromptVersionRead> {
  const response = await apiClient.patch<PromptVersionRead>(
    `/prompts/${encodeURIComponent(name)}/versions/${version}/activate`,
  );
  return response.data;
}
