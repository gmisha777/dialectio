import type { FeatureCollection, Point } from "geojson";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ConceptSummary = {
  id: number;
  wikidata_id: string | null;
  gloss_en: string;
  gloss_uk: string | null;
  description_en: string | null;
  description_uk: string | null;
};

export type SearchHit = {
  concept: ConceptSummary;
  matched_spelling: string;
  matched_language_en: string;
  matched_language_uk: string | null;
};

export type Audio = {
  url: string;
  license: string;
  speaker: string | null;
  is_synthetic: boolean;
};

export type Form = {
  spelling: string;
  ipa: string | null;
  transliteration: string | null;
  is_primary: boolean;
  external_id: string | null;
  audio: Audio[];
};

export type LanguageForms = {
  variety_id: number;
  iso639_3: string | null;
  name_en: string;
  name_uk: string | null;
  region_codes: string[];
  forms: Form[];
};

export type LabelProps = { code: string; text: string; name_en: string; name_uk: string | null };

export type ConceptDetail = ConceptSummary & {
  languages: LanguageForms[];
  labels: FeatureCollection<Point, LabelProps>;
};

/** UI locale -> ISO 639-3 code used to break ties between identical spellings. */
export const LOCALE_LANGUAGE: Record<string, string> = { uk: "ukr", en: "eng" };

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { signal });
  if (!response.ok) throw new Error(`${response.status} ${path}`);
  return response.json() as Promise<T>;
}

export function searchWords(q: string, locale: string, signal?: AbortSignal) {
  const params = new URLSearchParams({ q, prefer: LOCALE_LANGUAGE[locale] ?? "eng" });
  return getJson<SearchHit[]>(`/api/search?${params}`, signal);
}

export function getConcept(id: number, signal?: AbortSignal) {
  return getJson<ConceptDetail>(`/api/concepts/${id}`, signal);
}

/** Pick the Ukrainian or English variant of a localized field pair. */
export function localized(locale: string, en: string, uk: string | null): string;
export function localized(locale: string, en: string | null, uk: string | null): string | null;
export function localized(locale: string, en: string | null, uk: string | null) {
  return locale === "uk" ? (uk ?? en) : (en ?? uk);
}
