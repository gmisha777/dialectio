import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import InfoPage, { externalLink, GITHUB_ISSUES_URL } from "@/components/InfoPage";
import { pageMetadata } from "@/lib/metadata";

const SECTIONS = ["contrib", "ip", "browser", "third"] as const;

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/privacy">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Privacy" });
  return pageMetadata(locale, "/privacy", t("title"), t("metaDescription"));
}

export default async function PrivacyPage({ params }: PageProps<"/[locale]/privacy">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("Privacy");

  return (
    <InfoPage title={t("title")}>
      <p className="text-sm opacity-70">{t("updated")}</p>
      <p>{t("intro")}</p>
      {SECTIONS.map((section) => (
        <section key={section} className="space-y-4">
          <h2>{t(`${section}Title`)}</h2>
          <p>{t(section)}</p>
        </section>
      ))}
      <h2>{t("deleteTitle")}</h2>
      <p>{t.rich("delete", { link: externalLink(GITHUB_ISSUES_URL) })}</p>
    </InfoPage>
  );
}
