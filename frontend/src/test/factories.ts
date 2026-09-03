import type { LLMRequestRead } from "../api/types";

export function makeRequest(overrides: Partial<LLMRequestRead> = {}): LLMRequestRead {
  return {
    request_id: "11111111-1111-1111-1111-111111111111",
    trace_id: "22222222-2222-2222-2222-222222222222",
    user_id: "33333333-3333-3333-3333-333333333333",
    model: "gpt-4o-mini",
    provider: "openai",
    input_tokens: 10,
    output_tokens: 5,
    total_tokens: 15,
    estimated_cost: "0.001200",
    latency_ms: 420,
    status: "success",
    cache_hit: false,
    error: null,
    created_at: "2026-08-31T12:00:00Z",
    ...overrides,
  };
}
