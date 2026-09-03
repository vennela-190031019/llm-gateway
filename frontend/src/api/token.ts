// Small, framework-agnostic wrapper around token storage so both the
// axios interceptors (client.ts) and the auth context (useAuth.ts) read
// and write the same place without importing each other.

const STORAGE_KEY = "llm-gateway:access-token";

export function getToken(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(STORAGE_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(STORAGE_KEY);
}
