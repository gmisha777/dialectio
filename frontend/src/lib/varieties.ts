import { API_URL, localized } from "@/lib/api";

export type Variety = {
  code: string;
  kind: "language" | "dialect";
  name_en: string;
  name_uk: string | null;
  parent_code: string | null;
};

export async function listPublicVarieties(): Promise<Variety[]> {
  const response = await fetch(`${API_URL}/api/varieties`);
  if (!response.ok) throw new Error(`${response.status} /api/varieties`);
  return response.json();
}

/** Ukrainian and its dialects first (the project's focus), then other languages by name. */
export function sortVarieties<T extends Omit<Variety, "parent_code">>(
  varieties: T[],
  locale: string,
): T[] {
  const focus = (v: T) => (v.code === "ukr" || v.code.startsWith("ukr-") ? 0 : 1);
  return [...varieties].sort(
    (a, b) =>
      focus(a) - focus(b) ||
      Number(a.kind === "dialect") - Number(b.kind === "dialect") ||
      localized(locale, a.name_en, a.name_uk).localeCompare(localized(locale, b.name_en, b.name_uk)),
  );
}
