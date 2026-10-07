import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { cache } from "react";

import Explorer from "@/components/Explorer";
import { routing } from "@/i18n/routing";
import { type ConceptDetail, getConceptBySlug, localized, SITE_URL } from "@/lib/api";

// Languages quoted first in the page description (most searched), then the rest.
const DESCRIPTION_LANGUAGES = ["eng", "ukr", "deu", "fra", "spa", "pol", "ita"];
const DESCRIPTION_EXAMPLES = 5;

// generateMetadata and the page both need the concept; fetch it once per request.
const loadConcept = cache(getConceptBySlug);

function examples(concept: ConceptDetail, locale: string): string {
  const order = (iso: string | null) => {
    const i = DESCRIPTION_LANGUAGES.indexOf(iso ?? "");
    return i === -1 ? DESCRIPTION_LANGUAGES.length : i;
  };
  return [...concept.languages]
    .sort((a, b) => order(a.iso639_3) - order(b.iso639_3))
    .slice(0, DESCRIPTION_EXAMPLES)
    .map((lang) => `${lang.forms[0].spelling} (${localized(locale, lang.name_en, lang.name_uk)})`)
    .join(", ");
}

// Homonyms ("bark" the sound / "bark" of a tree) get the Wikidata id in their slug.
const HOMONYM_SLUG = /-q\d+$/;
const TITLE_HINT_LENGTH = 40;

/** The word for titles; homonyms get a short hint from the description so titles stay unique. */
function titleWord(concept: ConceptDetail, locale: string): string {
  const word = localized(locale, concept.gloss_en, concept.gloss_uk);
  const description = localized(locale, concept.description_en, concept.description_uk);
  if (!description || !HOMONYM_SLUG.test(concept.slug ?? "")) return word;
  const hint =
    description.length > TITLE_HINT_LENGTH
      ? `${description.slice(0, TITLE_HINT_LENGTH).trimEnd()}…`
      : description;
  return `${word} (${hint})`;
}

function pageUrl(locale: string, slug: string) {
  return `${SITE_URL}/${locale}/word/${slug}`;
}

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/word/[slug]">): Promise<Metadata> {
  const { locale, slug } = await params;
  const concept = await loadConcept(slug);
  if (!concept) return {};
  const t = await getTranslations({ locale, namespace: "Word" });
  const word = localized(locale, concept.gloss_en, concept.gloss_uk);

  return {
    title: t("title", { word: titleWord(concept, locale) }),
    description: t("description", {
      word,
      examples: examples(concept, locale),
      count: concept.languages.filter((l) => l.kind === "language").length,
    }),
    alternates: {
      canonical: pageUrl(locale, slug),
      languages: {
        ...Object.fromEntries(routing.locales.map((l) => [l, pageUrl(l, slug)])),
        "x-default": pageUrl(routing.defaultLocale, slug),
      },
    },
  };
}

export default async function WordPage({ params }: PageProps<"/[locale]/word/[slug]">) {
  const { locale, slug } = await params;
  setRequestLocale(locale);
  const concept = await loadConcept(slug);
  if (!concept) notFound();

  return <Explorer key={slug} initialConcept={concept} />;
}
