import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as promptsApi from "../api/prompts";
import type { PromptTemplateDetailRead, PromptTemplateRead } from "../api/types";
import { Prompts } from "./Prompts";

vi.mock("../api/prompts");

function renderPrompts() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Prompts />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const template: PromptTemplateRead = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "greeting",
  description: "Says hello",
  owner_id: "u1",
  created_at: "2026-01-01T00:00:00Z",
};

const templateDetail: PromptTemplateDetailRead = {
  ...template,
  versions: [
    {
      id: "22222222-2222-2222-2222-222222222222",
      version: 1,
      template_text: "Hi {name}",
      variables: ["name"],
      model: "gpt-4o-mini",
      temperature: 1,
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
    },
  ],
};

describe("Prompts", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the template list without crashing", async () => {
    vi.mocked(promptsApi.listPromptTemplates).mockResolvedValue([template]);

    renderPrompts();

    expect(await screen.findByText("greeting")).toBeInTheDocument();
    expect(screen.getByText("Says hello")).toBeInTheDocument();
  });

  it("shows a template's versions when selected", async () => {
    vi.mocked(promptsApi.listPromptTemplates).mockResolvedValue([template]);
    vi.mocked(promptsApi.getPromptTemplate).mockResolvedValue(templateDetail);
    const user = userEvent.setup();

    renderPrompts();

    await user.click(await screen.findByText("greeting"));

    expect(await screen.findByText("v1")).toBeInTheDocument();
    expect(screen.getByText("gpt-4o-mini")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("creating a template calls the API with the entered name", async () => {
    vi.mocked(promptsApi.listPromptTemplates).mockResolvedValue([]);
    vi.mocked(promptsApi.createPromptTemplate).mockResolvedValue({
      id: "33333333-3333-3333-3333-333333333333",
      name: "new-template",
      description: null,
      owner_id: "u1",
      created_at: "2026-01-01T00:00:00Z",
    });
    vi.mocked(promptsApi.getPromptTemplate).mockResolvedValue({
      id: "33333333-3333-3333-3333-333333333333",
      name: "new-template",
      description: null,
      owner_id: "u1",
      created_at: "2026-01-01T00:00:00Z",
      versions: [],
    });
    const user = userEvent.setup();

    renderPrompts();

    await user.click(await screen.findByRole("button", { name: "New Template" }));
    await user.type(screen.getByLabelText("Name"), "new-template");
    await user.click(screen.getByRole("button", { name: "Create" }));

    // react-query v5 calls mutationFn with a second (internal context)
    // argument — assert on the payload we actually care about.
    expect(vi.mocked(promptsApi.createPromptTemplate).mock.calls[0]?.[0]).toEqual({
      name: "new-template",
      description: undefined,
    });
  });
});
