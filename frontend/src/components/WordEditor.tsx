"use client";

import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, useEffect, useState } from "react";

import { localized } from "@/lib/api";
import {
  addForm,
  approveForm,
  deleteForm,
  type EditorConcept,
  EditorError,
  type EditorForm,
  listConcepts,
} from "@/lib/editor";

const LANG = "ukr";

const isApproved = (form: EditorForm) => form.status === "approved";
const TOKEN_KEY = "dialectio.editorToken";

function readToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

function saveToken(token: string) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // storage unavailable (private mode): token just isn't remembered
  }
}

function ConceptRow({
  concept,
  token,
  onChange,
}: {
  concept: EditorConcept;
  token: string;
  onChange: (forms: EditorForm[]) => void;
}) {
  const t = useTranslations("Editor");
  const locale = useLocale();
  const [spelling, setSpelling] = useState("");
  const [ipa, setIpa] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!spelling.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const form = await addForm(token, {
        concept_id: concept.id,
        iso639_3: LANG,
        spelling,
        ipa: ipa.trim() || null,
      });
      onChange([...concept.forms, form]);
      setSpelling("");
      setIpa("");
    } catch (err) {
      setError(err instanceof EditorError && err.status === 409 ? t("duplicate") : t("saveError"));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (form: EditorForm) => {
    setError(null);
    try {
      await deleteForm(token, form.id);
      // the server may promote another approved word to primary; mirror the simple case
      const rest = concept.forms.filter((f) => f.id !== form.id);
      const next = rest.find(isApproved);
      if (form.is_primary && next && !rest.some((f) => f.is_primary)) {
        onChange(rest.map((f) => (f === next ? { ...f, is_primary: true } : f)));
      } else {
        onChange(rest);
      }
    } catch {
      setError(t("saveError"));
    }
  };

  const approve = async (form: EditorForm) => {
    setError(null);
    try {
      const updated = await approveForm(token, form.id);
      onChange(concept.forms.map((f) => (f.id === form.id ? updated : f)));
    } catch {
      setError(t("saveError"));
    }
  };

  const description = localized(locale, concept.description_en, concept.description_uk);

  return (
    <li className="grid gap-2 border-b border-black/10 py-3 md:grid-cols-[1fr_1fr] dark:border-white/10">
      <div>
        <div className="font-medium">
          {localized(locale, concept.gloss_en, concept.gloss_uk)}
          {concept.wikidata_id && (
            <a
              href={`https://www.wikidata.org/wiki/${concept.wikidata_id}`}
              target="_blank"
              rel="noreferrer"
              className="ml-2 text-xs font-normal opacity-50 underline"
            >
              {concept.wikidata_id}
            </a>
          )}
        </div>
        {description && <div className="text-sm opacity-70">{description}</div>}
        <div className="mt-1 text-xs opacity-60">
          {Object.entries(concept.hints)
            .map(([lang, word]) => `${lang}: ${word}`)
            .join(" · ")}
        </div>
      </div>
      <div>
        <div className="mb-1 flex flex-wrap gap-1">
          {concept.forms.map((form) => (
            <span
              key={form.id}
              title={isApproved(form) ? (form.source ?? undefined) : t("draftHint")}
              className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-sm ${
                !isApproved(form)
                  ? "border border-dashed border-amber-500 bg-amber-500/10"
                  : form.is_primary
                    ? "bg-blue-500/15 font-semibold"
                    : "bg-black/5 dark:bg-white/10"
              }`}
            >
              {form.spelling}
              {form.ipa && <span className="font-mono text-xs opacity-70">{form.ipa}</span>}
              {!isApproved(form) && (
                <button
                  type="button"
                  onClick={() => approve(form)}
                  aria-label={t("approve", { word: form.spelling })}
                  className="font-semibold text-green-700 hover:text-green-500 dark:text-green-400"
                >
                  ✓
                </button>
              )}
              {form.editable && (
                <button
                  type="button"
                  onClick={() => remove(form)}
                  aria-label={t("delete", { word: form.spelling })}
                  className="opacity-60 hover:opacity-100"
                >
                  ✕
                </button>
              )}
            </span>
          ))}
        </div>
        <form onSubmit={submit} className="flex gap-2">
          <input
            value={spelling}
            onChange={(e) => setSpelling(e.target.value)}
            placeholder={t("wordPlaceholder")}
            aria-label={t("wordPlaceholder")}
            className="min-w-0 flex-1 rounded border border-black/15 bg-transparent px-2 py-1 dark:border-white/20"
          />
          <input
            value={ipa}
            onChange={(e) => setIpa(e.target.value)}
            placeholder={t("ipaPlaceholder")}
            aria-label={t("ipaPlaceholder")}
            className="w-28 rounded border border-black/15 bg-transparent px-2 py-1 font-mono dark:border-white/20"
          />
          <button
            type="submit"
            disabled={busy || !spelling.trim()}
            className="rounded bg-blue-600 px-3 py-1 text-white disabled:opacity-40"
          >
            {t("add")}
          </button>
        </form>
        {error && <div className="mt-1 text-sm text-red-600">{error}</div>}
      </div>
    </li>
  );
}

export default function WordEditor() {
  const t = useTranslations("Editor");
  const locale = useLocale();
  const [token, setToken] = useState("");
  const [tokenInput, setTokenInput] = useState("");
  const [concepts, setConcepts] = useState<EditorConcept[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [onlyMissing, setOnlyMissing] = useState(true);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    // localStorage is only available in the browser, after hydration.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setToken(readToken());
  }, []);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    listConcepts(token, LANG)
      .then((result) => {
        if (cancelled) return;
        setConcepts(result);
        setError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setConcepts(null);
        setError(
          err instanceof EditorError && err.status === 401
            ? t("badToken")
            : err instanceof EditorError && err.status === 503
              ? t("disabled")
              : t("loadError"),
        );
      });
    return () => {
      cancelled = true;
    };
  }, [token, t]);

  const login = (e: FormEvent) => {
    e.preventDefault();
    saveToken(tokenInput.trim());
    setToken(tokenInput.trim());
  };

  const done = concepts?.filter((c) => c.forms.some(isApproved)).length ?? 0;
  const drafts = concepts?.filter((c) => c.forms.some((f) => !isApproved(f))).length ?? 0;
  const needle = filter.trim().toLowerCase();
  const visible = (concepts ?? []).filter(
    (c) =>
      (!onlyMissing || !c.forms.some(isApproved)) &&
      (!needle ||
        localized(locale, c.gloss_en, c.gloss_uk).toLowerCase().includes(needle) ||
        Object.values(c.hints).some((w) => w.toLowerCase().includes(needle))),
  );

  return (
    <main className="mx-auto min-h-0 w-full max-w-5xl flex-1 overflow-y-auto p-4">
      <h1 className="text-2xl font-semibold">{t("title")}</h1>
      <p className="mb-4 text-sm opacity-70">{t("intro")}</p>

      {(!token || error) && (
        <form onSubmit={login} className="mb-4 flex gap-2">
          <input
            type="password"
            value={tokenInput}
            onChange={(e) => setTokenInput(e.target.value)}
            placeholder={t("tokenPlaceholder")}
            aria-label={t("tokenPlaceholder")}
            className="w-80 rounded border border-black/15 bg-transparent px-2 py-1 dark:border-white/20"
          />
          <button type="submit" className="rounded bg-blue-600 px-3 py-1 text-white">
            {t("login")}
          </button>
        </form>
      )}
      {error && <p className="mb-4 text-red-600">{error}</p>}

      {concepts && (
        <>
          <div className="sticky top-0 z-10 flex flex-wrap items-center gap-4 bg-[var(--background)] py-2">
            <span className="font-medium">
              {t("progress", { done, total: concepts.length })}
            </span>
            {drafts > 0 && (
              <span className="rounded bg-amber-500/15 px-2 py-0.5 text-sm">
                {t("drafts", { count: drafts })}
              </span>
            )}
            <label className="flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                checked={onlyMissing}
                onChange={(e) => setOnlyMissing(e.target.checked)}
              />
              {t("onlyMissing")}
            </label>
            <input
              type="search"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder={t("filterPlaceholder")}
              aria-label={t("filterPlaceholder")}
              className="rounded border border-black/15 bg-transparent px-2 py-1 text-sm dark:border-white/20"
            />
          </div>
          <ul>
            {visible.map((concept) => (
              <ConceptRow
                key={concept.id}
                concept={concept}
                token={token}
                onChange={(forms) =>
                  setConcepts((all) =>
                    all ? all.map((c) => (c.id === concept.id ? { ...c, forms } : c)) : all,
                  )
                }
              />
            ))}
          </ul>
          {visible.length === 0 && <p className="py-4 opacity-70">{t("allDone")}</p>}
        </>
      )}
    </main>
  );
}
