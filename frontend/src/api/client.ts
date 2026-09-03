import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { clearToken, getToken } from "./token";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

/**
 * The backend's root, without the /api/v1 prefix — /metrics (Prometheus
 * exposition) and other infra endpoints live there, not under /api/v1.
 * See backend/app/main.py: everything else is mounted under API_PREFIX,
 * but the Prometheus scrape endpoint deliberately isn't.
 */
export const API_ROOT_URL = API_BASE_URL.replace(/\/api\/v1\/?$/, "");

// The one endpoint allowed to 401 without triggering a forced redirect —
// that's just a bad-credentials login attempt, not an expired session.
const LOGIN_PATH = "/auth/login";

/** Attaches the stored JWT (if any) as a Bearer token on every request. */
export function attachAuthToken(
  config: InternalAxiosRequestConfig,
): InternalAxiosRequestConfig {
  const token = getToken();
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
}

/**
 * On a 401 from anything other than the login attempt itself, the
 * stored token is stale/invalid: clear it and send the user back to
 * /login. Always re-rejects so callers (react-query, try/catch in
 * components) still see the failure.
 */
export function handleResponseError(error: AxiosError): Promise<never> {
  const isUnauthorized = error.response?.status === 401;
  const isLoginRequest = error.config?.url === LOGIN_PATH;

  if (isUnauthorized && !isLoginRequest) {
    clearToken();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.assign("/login");
    }
  }

  return Promise.reject(error);
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

apiClient.interceptors.request.use(attachAuthToken);
apiClient.interceptors.response.use((response) => response, handleResponseError);
