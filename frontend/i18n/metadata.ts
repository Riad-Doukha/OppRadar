import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import type titles from "@/messages/en/common.json";

type TitleKey = keyof (typeof titles)["titles"];

/** `export const generateMetadata = titled("login")` — a page <title> in the visitor's language. */
export const titled = (key: TitleKey) => async (): Promise<Metadata> => ({ title: (await getTranslations("common.titles"))(key) });
