import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
import "@testing-library/jest-dom/vitest";

// @testing-library/react's auto-cleanup only self-registers when it finds
// a *global* `afterEach` (it can't assume a test framework). We don't set
// vitest's `globals: true`, so that global never exists and DOM from one
// test silently leaks into the next unless we call cleanup() ourselves.
afterEach(() => {
  cleanup();
});

// jsdom doesn't implement ResizeObserver; recharts' <ResponsiveContainer>
// needs one to even mount.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (!("ResizeObserver" in globalThis)) {
  (globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }).ResizeObserver =
    ResizeObserverStub;
}
