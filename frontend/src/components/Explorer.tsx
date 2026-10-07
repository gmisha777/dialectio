"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";

import ConceptPanel from "@/components/ConceptPanel";
import HomePanel from "@/components/HomePanel";
import { InfoNav } from "@/components/InfoPage";
import LocaleSwitcher from "@/components/LocaleSwitcher";
import SearchBox from "@/components/SearchBox";
import WorldMap, { type SelectedRegion } from "@/components/WorldMap";
import { Link } from "@/i18n/navigation";
import {
  type ConceptDetail,
  type FeaturedConcept,
  getConcept,
  localized,
  type SearchHit,
} from "@/lib/api";

export default function Explorer({
  initialConcept = null,
  featured = [],
  preview = null,
}: {
  /** Concept rendered on the server for /[locale]/word/[slug] pages. */
  initialConcept?: ConceptDetail | null;
  /** Home page: concepts with interesting dialect words, listed in the panel. */
  featured?: FeaturedConcept[];
  /** Home page: the word of the day, shown on the map until another word is picked. */
  preview?: ConceptDetail | null;
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
  const panelRef = useRef<HTMLDivElement>(null);

  const showConcept = (detail: ConceptDetail, selected: SelectedRegion | null) => {
    setConcept(detail);
    setRegion(selected);
    setError(false);
    if (detail.slug) {
      // Shareable URL without re-rendering the page (keeps the map as it is).
      window.history.pushState(null, "", `/${locale}/word/${detail.slug}`);
      document.title = tWord("title", {
        word: localized(locale, detail.gloss_en, detail.gloss_uk),
      });
    }
  };

  const selectRegion = (selected: SelectedRegion | null) => {
    // A click on the home page's preview map opens the word of the day for that region.
    if (!concept && preview) {
      showConcept(preview, selected);
      getConcept(preview.id) // the server-rendered preview may be a few minutes old
        .then(setConcept)
        .catch(() => {});
    } else {
      setRegion(selected);
    }
    // On phones the panel is below the map: bring the filtered list into view.
    if (selected && window.matchMedia("(max-width: 767px)").matches) {
      panelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const openConcept = (conceptId: number) => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    getConcept(conceptId, controller.signal)
      .then((detail) => showConcept(detail, null))
      .catch((e: unknown) => {
        if (!controller.signal.aborted) {
          console.error(e);
          setError(true);
        }
      });
  };

  const shown = concept ?? preview;
  const highlightCodes = useMemo(
    () => (shown ? shown.languages.flatMap((lang) => lang.region_codes) : []),
    [shown],
  );

  return (
    <main className="flex h-full flex-col">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-black/10 px-4 py-3 dark:border-white/15">
        <Link href="/" className="text-xl font-semibold">
          Dialectio
        </Link>
        <SearchBox onSelect={(hit: SearchHit) => openConcept(hit.concept.id)} />
        <InfoNav className="hidden shrink-0 lg:flex" />
        <LocaleSwitcher />
      </header>
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <section className="relative min-h-[50vh] flex-1">
          <WorldMap
            highlightCodes={highlightCodes}
            labels={shown?.labels ?? null}
            selectedCode={region?.code ?? null}
            onSelectRegion={selectRegion}
          />
        </section>
        <div ref={panelRef} className="border-black/10 md:w-96 md:border-l dark:border-white/15">
          {concept ? (
            <ConceptPanel
              concept={concept}
              region={region}
              onClearRegion={() => setRegion(null)}
            />
          ) : !error && featured.length > 0 ? (
            <HomePanel
              featured={featured}
              wordOfDay={featured.find((c) => c.id === preview?.id) ?? null}
              onOpen={(c) => openConcept(c.id)}
            />
          ) : (
            <div className="space-y-4 p-4">
              <p className="text-sm opacity-70">{error ? t("loadError") : t("hint")}</p>
              <InfoNav />
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
