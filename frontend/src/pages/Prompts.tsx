import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  activatePromptVersion,
  createPromptTemplate,
  createPromptVersion,
  getPromptTemplate,
  listPromptTemplates,
  renderPromptTemplate,
} from "../api/prompts";
import type { PromptTemplateDetailRead } from "../api/types";
import { ErrorNotice } from "../components/ErrorNotice";
import { Modal } from "../components/Modal";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

export function Prompts() {
  const queryClient = useQueryClient();
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [isCreateModalOpen, setCreateModalOpen] = useState(false);

  const templatesQuery = useQuery({
    queryKey: ["prompts"],
    queryFn: () => listPromptTemplates(),
  });
  const detailQuery = useQuery({
    queryKey: ["prompts", selectedName],
    queryFn: () => getPromptTemplate(selectedName as string),
    enabled: selectedName !== null,
  });

  const createTemplateMutation = useMutation({
    mutationFn: createPromptTemplate,
    onSuccess: (template) => {
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
      setSelectedName(template.name);
      setCreateModalOpen(false);
      createTemplateMutation.reset();
    },
  });

  function refetchDetail() {
    queryClient.invalidateQueries({ queryKey: ["prompts", selectedName] });
  }

  return (
    <div className="page">
      <div className="page-header page-header-row">
        <div>
          <h1>Prompts</h1>
          <p className="text-muted">Manage reusable prompt templates and preview renders.</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setCreateModalOpen(true)}>
          New Template
        </button>
      </div>

      {templatesQuery.isError && <ErrorNotice message={errorMessage(templatesQuery.error)} />}

      <div className="split-layout">
        <div className="list-panel">
          <div className="list-panel-header">
            <h2>Templates</h2>
          </div>
          {templatesQuery.isLoading && <div className="page-loading">Loading…</div>}
          {templatesQuery.data && templatesQuery.data.length === 0 && (
            <div className="empty-state empty-state-inline">
              <p>No templates yet.</p>
            </div>
          )}
          <div className="list-items">
            {templatesQuery.data?.map((template) => (
              <button
                key={template.id}
                type="button"
                className={
                  "list-item" + (template.name === selectedName ? " list-item-active" : "")
                }
                onClick={() => setSelectedName(template.name)}
              >
                <div className="list-item-title">{template.name}</div>
                {template.description && (
                  <div className="list-item-subtitle">{template.description}</div>
                )}
              </button>
            ))}
          </div>
        </div>

        <div className="detail-panel">
          {!selectedName && (
            <div className="empty-state">
              <p>Select a template to view its versions, or create a new one.</p>
            </div>
          )}
          {selectedName && detailQuery.isLoading && (
            <div className="page-loading">Loading template…</div>
          )}
          {selectedName && detailQuery.isError && (
            <ErrorNotice message={errorMessage(detailQuery.error)} />
          )}
          {detailQuery.data && (
            <>
              <div className="panel">
                <h2>{detailQuery.data.name}</h2>
                {detailQuery.data.description && (
                  <p className="text-muted">{detailQuery.data.description}</p>
                )}
              </div>
              <div className="panel">
                <div className="section-title">Versions</div>
                <VersionList template={detailQuery.data} onActivated={refetchDetail} />
                <NewVersionForm templateName={detailQuery.data.name} onCreated={refetchDetail} />
              </div>
              <div className="panel">
                <RenderTester template={detailQuery.data} />
              </div>
            </>
          )}
        </div>
      </div>

      {isCreateModalOpen && (
        <Modal
          title="New Prompt Template"
          onClose={() => {
            setCreateModalOpen(false);
            createTemplateMutation.reset();
          }}
        >
          <NewTemplateForm
            onSubmit={(input) => createTemplateMutation.mutate(input)}
            isSubmitting={createTemplateMutation.isPending}
            error={
              createTemplateMutation.isError ? errorMessage(createTemplateMutation.error) : null
            }
          />
        </Modal>
      )}
    </div>
  );
}

function NewTemplateForm({
  onSubmit,
  isSubmitting,
  error,
}: {
  onSubmit: (input: { name: string; description?: string }) => void;
  isSubmitting: boolean;
  error: string | null;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit({ name, description: description.trim() ? description : undefined });
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <label className="field">
        <span>Name</span>
        <input
          type="text"
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="customer-support"
        />
      </label>
      <label className="field">
        <span>Description (optional)</span>
        <input
          type="text"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </label>
      {error && <ErrorNotice message={error} />}
      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
          {isSubmitting ? "Creating…" : "Create"}
        </button>
      </div>
    </form>
  );
}

function VersionList({
  template,
  onActivated,
}: {
  template: PromptTemplateDetailRead;
  onActivated: () => void;
}) {
  const activateMutation = useMutation({
    mutationFn: (version: number) => activatePromptVersion(template.name, version),
    onSuccess: onActivated,
  });

  if (template.versions.length === 0) {
    return <p className="text-muted">No versions yet — add one below.</p>;
  }

  return (
    <>
      <div className="table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              <th>Version</th>
              <th>Model</th>
              <th>Temperature</th>
              <th>Variables</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {template.versions.map((version) => (
              <tr key={version.id}>
                <td className="cell-strong">v{version.version}</td>
                <td>{version.model}</td>
                <td>{version.temperature}</td>
                <td>
                  <div className="chip-row">
                    {version.variables.map((name) => (
                      <span key={name} className="chip">
                        {name}
                      </span>
                    ))}
                  </div>
                </td>
                <td>
                  <span className={"pill " + (version.is_active ? "pill-success" : "pill-muted")}>
                    {version.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td>
                  {!version.is_active && (
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => activateMutation.mutate(version.version)}
                      disabled={activateMutation.isPending}
                    >
                      Activate
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {activateMutation.isError && (
        <ErrorNotice message={errorMessage(activateMutation.error)} />
      )}
    </>
  );
}

function NewVersionForm({
  templateName,
  onCreated,
}: {
  templateName: string;
  onCreated: () => void;
}) {
  const [templateText, setTemplateText] = useState("");
  const [variablesInput, setVariablesInput] = useState("");
  const [model, setModel] = useState("gpt-4o-mini");
  const [temperature, setTemperature] = useState(1);

  const mutation = useMutation({
    mutationFn: () =>
      createPromptVersion(templateName, {
        template_text: templateText,
        variables: variablesInput
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
        model,
        temperature,
      }),
    onSuccess: () => {
      setTemplateText("");
      setVariablesInput("");
      onCreated();
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <div className="section-title">Add Version</div>
      <label className="field">
        <span>Template text</span>
        <textarea
          required
          value={templateText}
          onChange={(event) => setTemplateText(event.target.value)}
          placeholder="Hi {name}, welcome to {place}!"
        />
      </label>
      <label className="field">
        <span>Variables (comma-separated)</span>
        <input
          type="text"
          value={variablesInput}
          onChange={(event) => setVariablesInput(event.target.value)}
          placeholder="name, place"
        />
      </label>
      <div className="form-row">
        <label className="field">
          <span>Model</span>
          <input
            type="text"
            required
            value={model}
            onChange={(event) => setModel(event.target.value)}
          />
        </label>
        <label className="field">
          <span>Temperature</span>
          <input
            type="number"
            step="0.1"
            min="0"
            max="2"
            value={temperature}
            onChange={(event) => setTemperature(Number(event.target.value))}
          />
        </label>
      </div>
      {mutation.isError && <ErrorNotice message={errorMessage(mutation.error)} />}
      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={mutation.isPending}>
          {mutation.isPending ? "Adding…" : "Add Version"}
        </button>
      </div>
    </form>
  );
}

function RenderTester({ template }: { template: PromptTemplateDetailRead }) {
  const activeVersion = template.versions.find((version) => version.is_active) ?? null;
  const [selectedVersion, setSelectedVersion] = useState<number | "">("");
  const [variableValues, setVariableValues] = useState<Record<string, string>>({});

  const effectiveVersion =
    selectedVersion === ""
      ? activeVersion
      : (template.versions.find((version) => version.version === selectedVersion) ?? null);
  const expectedVariables = effectiveVersion?.variables ?? [];

  useEffect(() => {
    setVariableValues({});
  }, [effectiveVersion?.id]);

  const renderMutation = useMutation({
    mutationFn: () =>
      renderPromptTemplate(
        template.name,
        variableValues,
        selectedVersion === "" ? undefined : selectedVersion,
      ),
  });

  return (
    <div>
      <div className="section-title">Try It</div>
      <div className="form">
        <label className="field">
          <span>Version</span>
          <select
            value={selectedVersion}
            onChange={(event) =>
              setSelectedVersion(event.target.value === "" ? "" : Number(event.target.value))
            }
          >
            <option value="">
              Latest active{activeVersion ? ` (v${activeVersion.version})` : ""}
            </option>
            {template.versions.map((version) => (
              <option key={version.id} value={version.version}>
                v{version.version}
                {version.is_active ? " (active)" : ""}
              </option>
            ))}
          </select>
        </label>
        {expectedVariables.length === 0 ? (
          <p className="text-muted">This version has no variables to fill in.</p>
        ) : (
          expectedVariables.map((name) => (
            <label className="field" key={name}>
              <span>{name}</span>
              <input
                type="text"
                value={variableValues[name] ?? ""}
                onChange={(event) =>
                  setVariableValues((prev) => ({ ...prev, [name]: event.target.value }))
                }
              />
            </label>
          ))
        )}
        <div className="form-actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => renderMutation.mutate()}
            disabled={renderMutation.isPending}
          >
            {renderMutation.isPending ? "Rendering…" : "Render"}
          </button>
        </div>
        {renderMutation.isError && (
          <ErrorNotice message={errorMessage(renderMutation.error)} />
        )}
        {renderMutation.data && (
          <div>
            <div className="section-title">
              Output (model: {renderMutation.data.model}, temperature:{" "}
              {renderMutation.data.temperature}, version: {renderMutation.data.version})
            </div>
            <div className="render-output">{renderMutation.data.content}</div>
          </div>
        )}
      </div>
    </div>
  );
}
