"use client";

import { useLocale, useTranslations } from "next-intl";

import { useState } from "react";

import ContributeDialog from "@/components/ContributeDialog";
import type { SelectedRegion } from "@/components/WorldMap";
import {
  type Audio as AudioInfo,
  API_URL,
  type ConceptDetail,
  type LanguageForms,
  localized,
} from "@/lib/api";

function playAudio(url: string) {
  // Generated audio is served by the API under a relative /media/... path.
  const src = url.startsWith("/") ? `${API_URL}${url}` : url;
  new Audio(src).play().catch((e: unknown) => console.error(e));
}

function AudioButtons({ audio }: { audio: AudioInfo[] }) {
  const t = useTranslations("Panel");
  return (
    <span className="inline-flex gap-1">
      {audio.map((a, i) => (
        <button
          key={a.url}
          type="button"
          onClick={() => playAudio(a.url)}
          title={[a.speaker, a.license, a.is_synthetic ? t("synthetic") : null]
            .filter(Boolean)
            .join(" · ")}
          aria-label={a.is_synthetic ? t("playSynthetic") : t("play", { n: i + 1 })}
          className={`rounded-full border px-2 text-sm hover:bg-blue-500/10 ${
            a.is_synthetic ? "border-dashed border-current/30 opacity-80" : "border-current/20"
          }`}
        >
          ▶{audio.length > 1 && !a.is_synthetic ? ` ${i + 1}` : ""}
          {a.is_synthetic && <span className="ml-1 text-[10px] uppercase">{t("tts")}</span>}
        </button>
      ))}
    </span>
  );
}

function Approximate() {
  const t = useTranslations("Panel");
  return (
    <span title={t("unverified")} aria-label={t("unverified")} className="cursor-help text-sm opacity-60">
      ≈
    </span>
  );
}

function LanguageCard({ language }: { language: LanguageForms }) {
  const locale = useLocale();
  const t = useTranslations("Panel");
  const [primary, ...others] = language.forms;

  return (
    <li
      className={`border-b border-black/10 py-3 dark:border-white/10 ${
        language.kind === "dialect" ? "ml-3 border-l-2 border-l-violet-400 pl-3" : ""
      }`}
    >
      <div className="text-xs uppercase tracking-wide opacity-60">
        {localized(locale, language.name_en, language.name_uk)}
      </div>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-xl font-semibold">{primary.spelling}</span>
        {primary.unverified && <Approximate />}
        {primary.ipa && <span className="font-mono text-sm opacity-80">{primary.ipa}</span>}
        <AudioButtons audio={primary.audio} />
      </div>
      {others.length > 0 && (
        <div className="mt-1 text-sm opacity-70">
          {t("alsoSaid")}{" "}
          {others.map((form, i) => (
            <span key={form.spelling}>
              {i > 0 && ", "}
              {form.spelling}
              {form.ipa && <span className="font-mono"> {form.ipa}</span>}
              {form.audio.length > 0 && (
                <>
                  {" "}
                  <AudioButtons audio={form.audio} />
                </>
              )}
            </span>
          ))}
        </div>
      )}
    </li>
  );
}

export default function ConceptPanel({
  concept,
  region,
  onClearRegion,
}: {
  concept: ConceptDetail;
  region: SelectedRegion | null;
  onClearRegion: () => void;
}) {
  const locale = useLocale();
  const t = useTranslations("Panel");
  const description = localized(locale, concept.description_en, concept.description_uk);
  const [contributing, setContributing] = useState(false);

  // A region shows its own varieties (dialects, regional languages) and its country's languages.
  const languages = region
    ? concept.languages.filter(
        (lang) =>
          lang.region_codes.includes(region.code) ||
          (region.parentCode !== null && lang.region_codes.includes(region.parentCode)),
      )
    : concept.languages;

  return (
    <aside className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-black/10 p-4 dark:border-white/10">
        <h1 className="text-lg font-semibold">
          {localized(locale, concept.gloss_en, concept.gloss_uk)}
        </h1>
        {description && <p className="text-sm opacity-70">{description}</p>}
        <p className="mt-1 text-xs opacity-60">
          {t("languageCount", { count: concept.languages.length })}
        </p>
        {region && (
          <button
            type="button"
            onClick={onClearRegion}
            className="mt-2 rounded-md bg-blue-500/10 px-2 py-1 text-sm"
          >
            {region.name} ✕
          </button>
        )}
      </div>
      <button
        type="button"
        onClick={() => setContributing(true)}
        className="mx-4 mt-3 rounded-md border border-dashed border-blue-500/60 px-3 py-2 text-left text-sm text-blue-700 hover:bg-blue-500/10 dark:text-blue-300"
      >
        {t("contribute")}
      </button>
      {contributing && (
        <ContributeDialog
          conceptId={concept.id}
          conceptName={localized(locale, concept.gloss_en, concept.gloss_uk)}
          regionCode={region?.code ?? null}
          onClose={() => setContributing(false)}
        />
      )}
      <ul className="flex-1 overflow-y-auto px-4">
        {languages.length === 0 && <li className="py-3 text-sm opacity-60">{t("noWords")}</li>}
        {languages.map((language) => (
          <LanguageCard key={language.variety_id} language={language} />
        ))}
      </ul>
      <p className="border-t border-black/10 p-3 text-xs opacity-60 dark:border-white/10">
        {t.rich("attribution", {
          wikidata: (chunks) => (
            <a className="underline" href="https://www.wikidata.org/wiki/Wikidata:Lexicographical_data">
              {chunks}
            </a>
          ),
          commons: (chunks) => (
            <a className="underline" href="https://commons.wikimedia.org/">
              {chunks}
            </a>
          ),
        })}
      </p>
    </aside>
  );
}
