"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useId, useState } from "react";

import { localized, searchWords, type SearchHit } from "@/lib/api";

const DEBOUNCE_MS = 250;

export default function SearchBox({ onSelect }: { onSelect: (hit: SearchHit) => void }) {
  const t = useTranslations("Search");
  const locale = useLocale();
  const listId = useId();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [error, setError] = useState(false);

  useEffect(() => {
    const q = query.trim();
    if (!q) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      searchWords(q, locale, controller.signal)
        .then((result) => {
          setHits(result);
          setActive(0);
          setError(false);
        })
        .catch((e: unknown) => {
          if (!controller.signal.aborted) {
            console.error(e);
            setError(true);
          }
        });
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, locale]);

  const choose = (hit: SearchHit) => {
    onSelect(hit);
    setQuery(hit.matched_spelling);
    setOpen(false);
  };

  const showList = open && query.trim().length > 0;

  return (
    <div className="relative w-full max-w-md">
      <input
        type="search"
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-label={t("label")}
        placeholder={t("placeholder")}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          if (!e.target.value.trim()) setHits([]);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") setActive((i) => Math.min(i + 1, hits.length - 1));
          else if (e.key === "ArrowUp") setActive((i) => Math.max(i - 1, 0));
          else if (e.key === "Enter" && hits[active]) choose(hits[active]);
          else if (e.key === "Escape") setOpen(false);
        }}
        className="w-full rounded-md border border-black/15 bg-transparent px-3 py-1.5 dark:border-white/20"
      />
      {showList && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-20 mt-1 max-h-96 w-full overflow-auto rounded-md border border-black/10 bg-white text-black shadow-lg"
        >
          {error && <li className="px-3 py-2 text-sm text-red-700">{t("error")}</li>}
          {!error && hits.length === 0 && (
            <li className="px-3 py-2 text-sm text-black/60">{t("noResults")}</li>
          )}
          {hits.map((hit, i) => {
            const { concept } = hit;
            const description = localized(locale, concept.description_en, concept.description_uk);
            return (
              <li
                key={concept.id}
                role="option"
                aria-selected={i === active}
                // mousedown fires before the input's blur, which would close the list first
                onMouseDown={(e) => {
                  e.preventDefault();
                  choose(hit);
                }}
                onMouseEnter={() => setActive(i)}
                className={`cursor-pointer px-3 py-2 ${i === active ? "bg-blue-50" : ""}`}
              >
                <div className="font-medium">
                  {localized(locale, concept.gloss_en, concept.gloss_uk)}
                </div>
                {description && <div className="text-xs text-black/60">{description}</div>}
                <div className="text-xs text-black/50">
                  {t("matched", {
                    word: hit.matched_spelling,
                    language: localized(locale, hit.matched_language_en, hit.matched_language_uk),
                  })}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
