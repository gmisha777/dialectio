import type { Metadata } from "next";

import { routing } from "@/i18n/routing";
import { SITE_URL } from "@/lib/api";

/** Title, description and hreflang alternates for a page at `/<locale><path>`. */
export function pageMetadata(
  locale: string,
  path: string,
  title: string,
  description: string,
): Metadata {
  const url = (l: string) => `${SITE_URL}/${l}${path}`;
  return {
    title: `${title} · Dialectio`,
    description,
    alternates: {
      canonical: url(locale),
      languages: {
        ...Object.fromEntries(routing.locales.map((l) => [l, url(l)])),
        "x-default": url(routing.defaultLocale),
      },
    },
  };
}
