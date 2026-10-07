import { setRequestLocale } from "next-intl/server";

import Explorer from "@/components/Explorer";
import { getConceptBySlug, listFeaturedConcepts } from "@/lib/api";

const DAY_MS = 24 * 60 * 60 * 1000;

/** Days since the epoch (UTC): the word of the day changes at midnight UTC. */
function dayNumber() {
  return Math.floor(Date.now() / DAY_MS);
}

export default async function Home({ params }: PageProps<"/[locale]">) {
  const { locale } = await params;
  setRequestLocale(locale);

  // Word of the day: the featured concepts take turns, one per (UTC) day.
  const featured = await listFeaturedConcepts().catch(() => []);
  const wordOfDay = featured.length > 0 ? featured[dayNumber() % featured.length] : null;
  const preview = wordOfDay ? await getConceptBySlug(wordOfDay.slug).catch(() => null) : null;

  return <Explorer featured={featured} preview={preview} />;
}
