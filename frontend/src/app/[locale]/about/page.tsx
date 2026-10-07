import type { Metadata } from "next";
import { getFormatter, getTranslations, setRequestLocale } from "next-intl/server";

import InfoPage, { externalLink, GITHUB_ISSUES_URL } from "@/components/InfoPage";
import { getStats } from "@/lib/api";
import { pageMetadata } from "@/lib/metadata";

const HOW_STEPS = ["how1", "how2", "how3", "how4", "how5"] as const;

export async function generateMetadata({ params }: PageProps<"/[locale]/about">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "About" });
  return pageMetadata(locale, "/about", t("title"), t("metaDescription"));
}

export default async function AboutPage({ params }: PageProps<"/[locale]/about">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("About");
  const format = await getFormatter();
  const stats = await getStats().catch(() => null);

  return (
    <InfoPage title={t("title")}>
      <p>{t("intro")}</p>
      {stats && (
        <p>
          {t("numbers", {
            concepts: format.number(stats.concepts),
            languages: format.number(stats.languages),
            dialects: format.number(stats.dialects),
            words: format.number(stats.words),
            recordings: format.number(stats.recordings),
          })}
        </p>
      )}
      <h2>{t("howTitle")}</h2>
      <ol className="list-decimal space-y-2 pl-6">
        {HOW_STEPS.map((step) => (
          <li key={step}>{t(step)}</li>
        ))}
      </ol>
      <h2>{t("dialectsTitle")}</h2>
      <p>{t("dialects")}</p>
      <h2>{t("helpTitle")}</h2>
      <p>{t("help")}</p>
      <p>{t.rich("feedback", { link: externalLink(GITHUB_ISSUES_URL) })}</p>
    </InfoPage>
  );
}
