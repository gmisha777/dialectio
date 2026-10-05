"use client";

import { useTranslations } from "next-intl";
import { useMemo, useRef, useState } from "react";

import ConceptPanel from "@/components/ConceptPanel";
import LocaleSwitcher from "@/components/LocaleSwitcher";
import SearchBox from "@/components/SearchBox";
import WorldMap from "@/components/WorldMap";
import { type ConceptDetail, getConcept, type SearchHit } from "@/lib/api";

export default function Explorer() {
  const t = useTranslations("Explorer");
  const [concept, setConcept] = useState<ConceptDetail | null>(null);
  const [region, setRegion] = useState<{ code: string; name: string } | null>(null);
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
        <h1 className="text-xl font-semibold">Dialectio</h1>
        <SearchBox onSelect={selectHit} />
        <LocaleSwitcher />
      </header>
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <section className="relative min-h-[50vh] flex-1">
          <WorldMap
            highlightCodes={highlightCodes}
            labels={concept?.labels ?? null}
            selectedCode={region?.code ?? null}
            onSelectRegion={(code, name) => setRegion({ code, name })}
          />
        </section>
        <div className="border-black/10 md:w-96 md:border-l dark:border-white/15">
          {concept ? (
            <ConceptPanel
              concept={concept}
              regionCode={region?.code ?? null}
              regionName={region?.name ?? null}
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
