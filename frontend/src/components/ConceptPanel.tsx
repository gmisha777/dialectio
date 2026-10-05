"use client";

import { useLocale, useTranslations } from "next-intl";

import { type Audio as AudioInfo, type ConceptDetail, type LanguageForms, localized } from "@/lib/api";

function playAudio(url: string) {
  new Audio(url).play().catch((e: unknown) => console.error(e));
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
          aria-label={t("play", { n: i + 1 })}
          className="rounded-full border border-current/20 px-2 text-sm hover:bg-blue-500/10"
        >
          ▶{audio.length > 1 ? ` ${i + 1}` : ""}
        </button>
      ))}
    </span>
  );
}

function LanguageCard({ language }: { language: LanguageForms }) {
  const locale = useLocale();
  const t = useTranslations("Panel");
  const [primary, ...others] = language.forms;

  return (
    <li className="border-b border-black/10 py-3 dark:border-white/10">
      <div className="text-xs uppercase tracking-wide opacity-60">
        {localized(locale, language.name_en, language.name_uk)}
      </div>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-xl font-semibold">{primary.spelling}</span>
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
  regionCode,
  regionName,
  onClearRegion,
}: {
  concept: ConceptDetail;
  regionCode: string | null;
  regionName: string | null;
  onClearRegion: () => void;
}) {
  const locale = useLocale();
  const t = useTranslations("Panel");
  const description = localized(locale, concept.description_en, concept.description_uk);
  const languages = regionCode
    ? concept.languages.filter((lang) => lang.region_codes.includes(regionCode))
    : concept.languages;

  return (
    <aside className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-black/10 p-4 dark:border-white/10">
        <h2 className="text-lg font-semibold">
          {localized(locale, concept.gloss_en, concept.gloss_uk)}
        </h2>
        {description && <p className="text-sm opacity-70">{description}</p>}
        <p className="mt-1 text-xs opacity-60">
          {t("languageCount", { count: concept.languages.length })}
        </p>
        {regionCode && (
          <button
            type="button"
            onClick={onClearRegion}
            className="mt-2 rounded-md bg-blue-500/10 px-2 py-1 text-sm"
          >
            {regionName ?? regionCode} ✕
          </button>
        )}
      </div>
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
