"use client";

import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { API_URL, localized } from "@/lib/api";
import { listPublicVarieties, sortVarieties, type Variety } from "@/lib/varieties";

const MAX_RECORDING_MS = 10_000;
// Browsers record in different containers: Chrome/Firefox WebM/Ogg, Safari MP4.
const RECORDING_TYPES = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"];

type Status = "idle" | "sending" | "sent" | "error" | "tooMany";

function useRecorder() {
  const [recording, setRecording] = useState(false);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [error, setError] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stop = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  };

  const start = async () => {
    setError(false);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = RECORDING_TYPES.find((t) => MediaRecorder.isTypeSupported(t));
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      const chunks: Blob[] = [];
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        setBlob(new Blob(chunks, { type: recorder.mimeType.split(";")[0] }));
        setRecording(false);
      };
      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);
      timerRef.current = setTimeout(stop, MAX_RECORDING_MS);
    } catch {
      setError(true); // no microphone or permission denied
    }
  };

  useEffect(() => stop, []);

  return { recording, blob, error, start, stop, clear: () => setBlob(null) };
}

export default function ContributeDialog({
  conceptId,
  conceptName,
  defaultVariety,
  onClose,
}: {
  conceptId: number;
  conceptName: string;
  defaultVariety: string;
  onClose: () => void;
}) {
  const t = useTranslations("Contribute");
  const locale = useLocale();
  const [varieties, setVarieties] = useState<Variety[]>([]);
  const [variety, setVariety] = useState(defaultVariety);
  const [spelling, setSpelling] = useState("");
  const [place, setPlace] = useState("");
  const [contributor, setContributor] = useState("");
  const [consent, setConsent] = useState(false);
  const [website, setWebsite] = useState(""); // honeypot, hidden from people
  const [status, setStatus] = useState<Status>("idle");
  const recorder = useRecorder();
  const audioSrc = useMemo(
    () => (recorder.blob ? URL.createObjectURL(recorder.blob) : null),
    [recorder.blob],
  );
  useEffect(() => () => void (audioSrc && URL.revokeObjectURL(audioSrc)), [audioSrc]);

  useEffect(() => {
    listPublicVarieties()
      .then((result) => setVarieties(sortVarieties(result, locale)))
      .catch(() => setVarieties([]));
  }, [locale]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!spelling.trim() || !consent) return;
    setStatus("sending");
    const data = new FormData();
    data.append("concept_id", String(conceptId));
    data.append("variety", variety);
    data.append("spelling", spelling.trim());
    data.append("place", place.trim());
    data.append("contributor", contributor.trim());
    data.append("consent", "true");
    data.append("website", website);
    if (recorder.blob) {
      const extension = recorder.blob.type.includes("mp4") ? "m4a" : recorder.blob.type.split("/")[1];
      data.append("audio", recorder.blob, `recording.${extension}`);
    }
    try {
      const response = await fetch(`${API_URL}/api/contributions`, { method: "POST", body: data });
      setStatus(response.ok ? "sent" : response.status === 429 ? "tooMany" : "error");
    } catch {
      setStatus("error");
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="contribute-title"
        className="max-h-full w-full max-w-md overflow-y-auto rounded-lg bg-[var(--background)] p-5 shadow-xl"
      >
        <div className="mb-3 flex items-start justify-between gap-4">
          <h2 id="contribute-title" className="text-lg font-semibold">
            {t("title", { word: conceptName })}
          </h2>
          <button type="button" onClick={onClose} aria-label={t("close")} className="opacity-60">
            ✕
          </button>
        </div>

        {status === "sent" ? (
          <div className="space-y-4">
            <p>{t("thanks")}</p>
            <button type="button" onClick={onClose} className="rounded bg-blue-600 px-3 py-1.5 text-white">
              {t("close")}
            </button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-3 text-sm">
            <label className="block">
              <span className="mb-1 block opacity-70">{t("variety")}</span>
              <select
                value={variety}
                onChange={(e) => setVariety(e.target.value)}
                className="w-full rounded border border-black/15 bg-transparent px-2 py-1.5 dark:border-white/20"
              >
                {varieties.map((v) => (
                  <option key={v.code} value={v.code}>
                    {v.kind === "dialect" ? "— " : ""}
                    {localized(locale, v.name_en, v.name_uk)}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block opacity-70">{t("word")}</span>
              <input
                required
                maxLength={200}
                value={spelling}
                onChange={(e) => setSpelling(e.target.value)}
                className="w-full rounded border border-black/15 bg-transparent px-2 py-1.5 text-base dark:border-white/20"
              />
            </label>
            <label className="block">
              <span className="mb-1 block opacity-70">{t("place")}</span>
              <input
                maxLength={200}
                value={place}
                onChange={(e) => setPlace(e.target.value)}
                placeholder={t("placeHint")}
                className="w-full rounded border border-black/15 bg-transparent px-2 py-1.5 dark:border-white/20"
              />
            </label>
            <label className="block">
              <span className="mb-1 block opacity-70">{t("name")}</span>
              <input
                maxLength={100}
                value={contributor}
                onChange={(e) => setContributor(e.target.value)}
                className="w-full rounded border border-black/15 bg-transparent px-2 py-1.5 dark:border-white/20"
              />
            </label>
            {/* Honeypot: invisible to people, bots fill it in. */}
            <input
              type="text"
              name="website"
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
              tabIndex={-1}
              autoComplete="off"
              aria-hidden="true"
              className="absolute -left-[9999px] h-0 w-0 opacity-0"
            />

            <div>
              <span className="mb-1 block opacity-70">{t("recording")}</span>
              <div className="flex flex-wrap items-center gap-2">
                {recorder.recording ? (
                  <button
                    type="button"
                    onClick={recorder.stop}
                    className="rounded bg-red-600 px-3 py-1.5 text-white"
                  >
                    ■ {t("stop")}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={recorder.start}
                    className="rounded border border-current/30 px-3 py-1.5"
                  >
                    ● {recorder.blob ? t("recordAgain") : t("record")}
                  </button>
                )}
                {audioSrc && !recorder.recording && (
                  <>
                    <audio src={audioSrc} controls className="h-8 max-w-full" />
                    <button type="button" onClick={recorder.clear} className="opacity-60">
                      {t("removeRecording")}
                    </button>
                  </>
                )}
              </div>
              <p className="mt-1 text-xs opacity-60">
                {recorder.error ? t("micError") : t("recordingHint")}
              </p>
            </div>

            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                required
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-0.5"
              />
              <span className="text-xs opacity-80">{t("consent")}</span>
            </label>

            {status === "error" && <p className="text-red-600">{t("error")}</p>}
            {status === "tooMany" && <p className="text-red-600">{t("tooMany")}</p>}
            <button
              type="submit"
              disabled={status === "sending" || !spelling.trim() || !consent || recorder.recording}
              className="w-full rounded bg-blue-600 px-3 py-2 text-white disabled:opacity-40"
            >
              {status === "sending" ? t("sending") : t("send")}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
