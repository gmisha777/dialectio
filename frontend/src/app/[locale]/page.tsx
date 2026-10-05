import { setRequestLocale } from "next-intl/server";
import { use } from "react";

import Explorer from "@/components/Explorer";

export default function Home({ params }: PageProps<"/[locale]">) {
  const { locale } = use(params);
  setRequestLocale(locale);

  return <Explorer />;
}
