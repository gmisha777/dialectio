import type { FeatureCollection, Point } from "geojson";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
/** API address for server-side rendering (can be an internal URL in production). */
const SERVER_API_URL = process.env.API_INTERNAL_URL || API_URL;
/** Public address of the site, used for canonical URLs and the sitemap. */
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
/** How long server-rendered pages may reuse API data, in seconds (the page also refreshes
 * its data in the browser, so visitors see edits right away; this mainly bounds staleness
 * for search engines). */
const SERVER_REVALIDATE = 300;

export type ConceptSummary = {
  id: number;
  wikidata_id: string | null;
  slug: string | null;
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
  source: string | null;
  /** Not checked by a person or a dictionary: shown as possibly inaccurate. */
  unverified: boolean;
  audio: Audio[];
};

export type LanguageForms = {
  variety_id: number;
  /** "ukr", or a dialect like "ukr-hutsul" */
  code: string;
  kind: "language" | "dialect_group" | "dialect";
  parent_code: string | null;
  iso639_3: string | null;
  name_en: string;
  name_uk: string | null;
  region_codes: string[];
  forms: Form[];
};

export type LabelProps = {
  code: string;
  /** "country", or "adm1" for first-level regions (oblasts) shown when zoomed in */
  level: "country" | "adm1";
  parent_code: string | null;
  /** The label shows dialect words */
  dialect: boolean;
  text: string;
  name_en: string;
  name_uk: string | null;
  /** Label importance, lower = more important; labels arrive sorted by it. */
  rank: number;
};

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

export type ConceptLink = { slug: string; gloss_en: string; gloss_uk: string | null };

async function getServerJson<T>(path: string): Promise<T | null> {
  const response = await fetch(`${SERVER_API_URL}${path}`, {
    next: { revalidate: SERVER_REVALIDATE },
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`${response.status} ${path}`);
  return response.json() as Promise<T>;
}

/** Server-side: concept page data, or null when the slug does not exist. */
export function getConceptBySlug(slug: string) {
  return getServerJson<ConceptDetail>(`/api/concepts/by-slug/${encodeURIComponent(slug)}`);
}

/** Server-side: every concept that has a page. */
export async function listConceptLinks() {
  return (await getServerJson<ConceptLink[]>("/api/concepts")) ?? [];
}

/** Pick the Ukrainian or English variant of a localized field pair. */
export function localized(locale: string, en: string, uk: string | null): string;
export function localized(locale: string, en: string | null, uk: string | null): string | null;
export function localized(locale: string, en: string | null, uk: string | null) {
  return locale === "uk" ? (uk ?? en) : (en ?? uk);
}

export type SourceStats = {
  name: string;
  url: string | null;
  license: string;
  words: number;
  recordings: number;
};

export type Stats = {
  concepts: number;
  languages: number;
  dialects: number;
  words: number;
  recordings: number;
  synthetic_recordings: number;
  sources: SourceStats[];
};

/** Server-side: site-wide numbers and data sources. */
export function getStats() {
  return getServerJson<Stats>("/api/stats");
}
