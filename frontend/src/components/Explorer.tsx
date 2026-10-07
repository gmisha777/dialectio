"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";

import ConceptPanel from "@/components/ConceptPanel";
import LocaleSwitcher from "@/components/LocaleSwitcher";
import SearchBox from "@/components/SearchBox";
import WorldMap, { type SelectedRegion } from "@/components/WorldMap";
import { Link } from "@/i18n/navigation";
import { type ConceptDetail, getConcept, localized, type SearchHit } from "@/lib/api";

export default function Explorer({
  initialConcept = null,
}: {
  /** Concept rendered on the server for /[locale]/word/[slug] pages. */
  initialConcept?: ConceptDetail | null;
}) {
  const t = useTranslations("Explorer");
  const tWord = useTranslations("Word");
  const locale = useLocale();
  const [concept, setConcept] = useState<ConceptDetail | null>(initialConcept);

  // The server-rendered page may be a few minutes old (cache); load the current data so
  // edits and newly approved words show up immediately.
  useEffect(() => {
    if (!initialConcept) return;
    const controller = new AbortController();
    getConcept(initialConcept.id, controller.signal)
      .then(setConcept)
      .catch(() => {}); // keep the server-rendered data
    return () => controller.abort();
  }, [initialConcept]);
  const [region, setRegion] = useState<SelectedRegion | null>(null);
  const [error, setError] = useState(false);
  const requestRef = useRef<AbortController | null>(null);

  const selectHit = (hit: SearchHit) => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    getConcept(hit.concept.id, controller.signal)
      .then((detail) => {
        setConcept(detail);
        setRegion(null);
        setError(false);
        if (detail.slug) {
          // Shareable URL without re-rendering the page (keeps the map as it is).
          window.history.pushState(null, "", `/${locale}/word/${detail.slug}`);
          document.title = tWord("title", {
            word: localized(locale, detail.gloss_en, detail.gloss_uk),
          });
        }
      })
      .catch((e: unknown) => {
        if (!controller.signal.aborted) {
          console.error(e);
          setError(true);
        }
      });
  };

  const highlightCodes = useMemo(
    () => (concept ? concept.languages.flatMap((lang) => lang.region_codes) : []),
    [concept],
  );

  return (
    <main className="flex h-full flex-col">
      <header className="flex items-center gap-4 border-b border-black/10 px-4 py-3 dark:border-white/15">
        <Link href="/" className="text-xl font-semibold">
          Dialectio
        </Link>
        <SearchBox onSelect={selectHit} />
        <LocaleSwitcher />
      </header>
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <section className="relative min-h-[50vh] flex-1">
          <WorldMap
            highlightCodes={highlightCodes}
            labels={concept?.labels ?? null}
            selectedCode={region?.code ?? null}
            onSelectRegion={setRegion}
          />
        </section>
        <div className="border-black/10 md:w-96 md:border-l dark:border-white/15">
          {concept ? (
            <ConceptPanel
              concept={concept}
              region={region}
              onClearRegion={() => setRegion(null)}
            />
          ) : (
            <p className="p-4 text-sm opacity-70">{error ? t("loadError") : t("hint")}</p>
          )}
        </div>
      </div>
    </main>
  );
}
