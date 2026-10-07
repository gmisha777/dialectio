import type { MetadataRoute } from "next";

import { INFO_PAGES } from "@/components/InfoPage";
import { routing } from "@/i18n/routing";
import { listConceptLinks, SITE_URL } from "@/lib/api";

// Rebuild the sitemap at most once an hour.
export const revalidate = 3600;

function alternates(path: string) {
  return {
    languages: Object.fromEntries(routing.locales.map((l) => [l, `${SITE_URL}/${l}${path}`])),
  };
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const concepts = await listConceptLinks();
  const paths = ["", ...INFO_PAGES.map((page) => `/${page}`), ...concepts.map((c) => `/word/${c.slug}`)];

  return paths.flatMap((path) =>
    routing.locales.map((locale) => ({
      url: `${SITE_URL}/${locale}${path}`,
      alternates: alternates(path),
    })),
  );
}
