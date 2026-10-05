"use client";

import { useLocale, useTranslations } from "next-intl";

import { usePathname, useRouter } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";

const LABELS: Record<(typeof routing.locales)[number], string> = {
  uk: "Українська",
  en: "English",
};

export default function LocaleSwitcher() {
  const t = useTranslations("Header");
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  return (
    <select
      aria-label={t("language")}
      value={locale}
      onChange={(e) => router.replace(pathname, { locale: e.target.value })}
      className="ml-auto rounded-md border border-black/15 bg-transparent px-2 py-1.5 dark:border-white/20"
    >
      {routing.locales.map((l) => (
        <option key={l} value={l}>
          {LABELS[l]}
        </option>
      ))}
    </select>
  );
}
