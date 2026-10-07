import { API_URL } from "@/lib/api";

export type EditorForm = {
  id: number;
  spelling: string;
  ipa: string | null;
  is_primary: boolean;
  /** "approved" words are public; "pending" drafts wait for review. */
  status: "approved" | "pending" | "submitted";
  source: string | null;
  editable: boolean;
  /** Visitor submissions only */
  contributor: string | null;
  place: string | null;
  audio_urls: string[];
};

export type Submission = {
  form: EditorForm;
  concept_id: number;
  concept_gloss_en: string;
  concept_gloss_uk: string | null;
  variety_code: string;
  variety_name_en: string;
  variety_name_uk: string | null;
};

export const listSubmissions = (token: string) => request<Submission[]>(token, "/submissions");

export type EditorConcept = {
  id: number;
  wikidata_id: string | null;
  gloss_en: string;
  gloss_uk: string | null;
  description_en: string | null;
  description_uk: string | null;
  hints: Record<string, string>;
  forms: EditorForm[];
};

export class EditorError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(token: string, path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}/api/editor${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", "X-Editor-Token": token, ...init.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new EditorError(response.status, body?.detail ?? response.statusText);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export type EditorVariety = {
  code: string;
  kind: "language" | "dialect";
  name_en: string;
  name_uk: string | null;
  parent_code: string | null;
};

export const listVarieties = (token: string) => request<EditorVariety[]>(token, "/varieties");

export const listConcepts = (token: string, variety: string) =>
  request<EditorConcept[]>(token, `/concepts?variety=${encodeURIComponent(variety)}`);

export const addForm = (
  token: string,
  form: { concept_id: number; variety: string; spelling: string; ipa: string | null },
) => request<EditorForm>(token, "/forms", { method: "POST", body: JSON.stringify(form) });

export const approveForm = (token: string, id: number) =>
  request<EditorForm>(token, `/forms/${id}/approve`, { method: "POST" });

/** Make this word the main one for its concept and language. */
export const setPrimaryForm = (token: string, id: number) =>
  request<EditorForm>(token, `/forms/${id}/primary`, { method: "POST" });

export const deleteForm = (token: string, id: number) =>
  request<void>(token, `/forms/${id}`, { method: "DELETE" });
