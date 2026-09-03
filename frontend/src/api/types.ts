// Mirrors backend/app/schemas/*.py and backend/app/models/*.py exactly —
// keep these in sync with the FastAPI response_models. Decimal fields
// (pydantic) serialize to JSON strings, not numbers — see estimated_cost,
// input_price_per_1k, output_price_per_1k, cost below.

export type UserRole = "ADMIN" | "USER";

export interface UserRead {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface ModelRead {
  id: string;
  name: string;
  provider_name: string;
  tier: string;
  input_price_per_1k: string;
  output_price_per_1k: string;
  is_active: boolean;
}

export type LLMRequestStatus = "success" | "error";

export interface LLMRequestRead {
  request_id: string;
  trace_id: string;
  user_id: string;
  model: string;
  provider: string | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost: string | null;
  latency_ms: number;
  status: LLMRequestStatus;
  cache_hit: boolean;
  error: string | null;
  created_at: string;
}

/** Aggregated over *all* of the current user's requests, not a capped page. */
export interface RequestsSummaryRead {
  total_requests: number;
  success_rate: number | null;
  average_latency_ms: number | null;
  total_tokens: number;
  total_cost: string;
  cache_hit_rate: number | null;
}
