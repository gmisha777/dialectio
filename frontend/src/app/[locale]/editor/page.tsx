import type { Metadata } from "next";
import { setRequestLocale } from "next-intl/server";
import { use } from "react";

import WordEditor from "@/components/WordEditor";

// Internal tool: keep it out of search engines.
export const metadata: Metadata = { robots: { index: false, follow: false } };

export default function EditorPage({ params }: PageProps<"/[locale]/editor">) {
  const { locale } = use(params);
  setRequestLocale(locale);

  return <WordEditor />;
}
