import type { Metadata } from "next";
import { getFormatter, getTranslations, setRequestLocale } from "next-intl/server";

import InfoPage from "@/components/InfoPage";
import { getStats } from "@/lib/api";
import { pageMetadata } from "@/lib/metadata";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/sources">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Sources" });
  return pageMetadata(locale, "/sources", t("title"), t("metaDescription"));
}

export default async function SourcesPage({ params }: PageProps<"/[locale]/sources">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("Sources");
  const format = await getFormatter();
  const stats = await getStats().catch(() => null);
  // Only sources that provide something visible (words or recordings); map data is described below.
  const sources = (stats?.sources ?? []).filter((s) => s.words > 0 || s.recordings > 0);

  return (
    <InfoPage title={t("title")}>
      <p>{t("intro")}</p>
      {sources.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-black/15 dark:border-white/20">
              <tr>
                <th className="py-2 pr-3 font-medium">{t("name")}</th>
                <th className="py-2 pr-3 font-medium">{t("license")}</th>
                <th className="py-2 pr-3 text-right font-medium">{t("words")}</th>
                <th className="py-2 text-right font-medium">{t("recordings")}</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((source) => (
                <tr key={source.name} className="border-b border-black/5 dark:border-white/10">
                  <td className="py-2 pr-3">
                    {source.url ? (
                      <a href={source.url} target="_blank" rel="noopener noreferrer">
                        {source.name}
                      </a>
                    ) : (
                      source.name
                    )}
                  </td>
                  <td className="py-2 pr-3">{source.license}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {source.words ? format.number(source.words) : "—"}
                  </td>
                  <td className="py-2 text-right tabular-nums">
                    {source.recordings ? format.number(source.recordings) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <h2>{t("mapTitle")}</h2>
      <p>{t("map")}</p>
      <h2>{t("ttsTitle")}</h2>
      <p>{t("tts")}</p>
      <h2>{t("ownTitle")}</h2>
      <p>{t("own")}</p>
    </InfoPage>
  );
}
