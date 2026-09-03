import { AxiosHeaders, type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { attachAuthToken, handleResponseError } from "./client";
import { clearToken, getToken, setToken } from "./token";

function buildConfig(): InternalAxiosRequestConfig {
  return { headers: new AxiosHeaders() } as InternalAxiosRequestConfig;
}

function buildAxiosError(status: number, url: string): AxiosError {
  return {
    isAxiosError: true,
    name: "AxiosError",
    message: "Request failed",
    toJSON: () => ({}),
    config: { url } as InternalAxiosRequestConfig,
    response: {
      status,
      statusText: "",
      data: {},
      headers: {},
      config: { url } as InternalAxiosRequestConfig,
    },
  } as AxiosError;
}

describe("attachAuthToken", () => {
  beforeEach(() => {
    clearToken();
  });

  it("attaches the stored token as a Bearer header", () => {
    setToken("abc123");

    const config = attachAuthToken(buildConfig());

    expect(config.headers.get("Authorization")).toBe("Bearer abc123");
  });

  it("leaves the Authorization header unset when no token is stored", () => {
    const config = attachAuthToken(buildConfig());

    expect(config.headers.get("Authorization")).toBeFalsy();
  });
});

describe("handleResponseError", () => {
  // jsdom's window.location.assign isn't a configurable property, so
  // vi.spyOn can't patch it directly — replace the whole `location`
  // object with a mutable stand-in for the duration of these tests.
  const originalLocation = window.location;
  let assignSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    clearToken();
    setToken("stale-token");
    assignSpy = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...originalLocation, pathname: "/requests", assign: assignSpy },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation,
    });
  });

  it("clears the token and redirects to /login on a 401 from a normal request", async () => {
    await expect(handleResponseError(buildAxiosError(401, "/requests"))).rejects.toBeTruthy();

    expect(getToken()).toBeNull();
    expect(assignSpy).toHaveBeenCalledWith("/login");
  });

  it("does not redirect on a 401 from the login endpoint itself", async () => {
    await expect(
      handleResponseError(buildAxiosError(401, "/auth/login")),
    ).rejects.toBeTruthy();

    expect(assignSpy).not.toHaveBeenCalled();
  });

  it("does not redirect and does not clear the token on non-401 errors", async () => {
    await expect(handleResponseError(buildAxiosError(500, "/requests"))).rejects.toBeTruthy();

    expect(assignSpy).not.toHaveBeenCalled();
    expect(getToken()).toBe("stale-token");
  });
});
