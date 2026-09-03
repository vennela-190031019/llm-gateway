import { apiClient } from "./client";
import type { Token, UserRead } from "./types";

/**
 * POST /auth/login expects OAuth2 "password" grant form fields
 * (username/password), not JSON — FastAPI's OAuth2PasswordRequestForm.
 * URLSearchParams makes axios send it as
 * application/x-www-form-urlencoded automatically.
 */
export async function login(email: string, password: string): Promise<Token> {
  const body = new URLSearchParams({ username: email, password });
  const response = await apiClient.post<Token>("/auth/login", body);
  return response.data;
}

export async function fetchCurrentUser(): Promise<UserRead> {
  const response = await apiClient.get<UserRead>("/auth/me");
  return response.data;
}
