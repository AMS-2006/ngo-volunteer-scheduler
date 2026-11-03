import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { apiPatch } from "@/lib/api";
import en from "@/locales/en";
import kn from "@/locales/kn";
import hi from "@/locales/hi";
import ta from "@/locales/ta";
import te from "@/locales/te";

export const LANGS = [
  { code: "en", label: "English" },
  { code: "kn", label: "ಕನ್ನಡ" },
  { code: "hi", label: "हिन्दी" },
  { code: "ta", label: "தமிழ்" },
  { code: "te", label: "తెలుగు" },
] as const;

const KEY = "vc_lang";
const saved = typeof localStorage !== "undefined" ? localStorage.getItem(KEY) : null;

i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, kn: { translation: kn }, hi: { translation: hi }, ta: { translation: ta }, te: { translation: te } },
  lng: saved ?? "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});
document.documentElement.lang = i18n.language;

/** Change UI language; persists locally and (when signed in) to the user's profile. */
export function setLanguage(code: string, persistServer = true) {
  if (!LANGS.some((l) => l.code === code)) return;
  i18n.changeLanguage(code);
  localStorage.setItem(KEY, code);
  document.documentElement.lang = code;
  if (persistServer) apiPatch("/auth/language", { preferred_language: code }).catch(() => undefined);
}

export default i18n;
