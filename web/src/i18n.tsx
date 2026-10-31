import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Lang = "en" | "hi";

const STRINGS = {
  skip: { en: "Skip to main content", hi: "मुख्य सामग्री पर जाएँ" },
  textSize: { en: "Text size", hi: "अक्षर आकार" },
  brandTagline: { en: "Citizen services, assisted", hi: "नागरिक सेवाएँ, आपके साथ" },
  navHome: { en: "Home", hi: "होम" },
  navSchemes: { en: "Know your schemes", hi: "योजनाएँ जानें" },
  navGrievance: { en: "Report a problem", hi: "शिकायत दर्ज करें" },
  navBoard: { en: "Accountability board", hi: "जवाबदेही बोर्ड" },
  navAgent: { en: "Agent room", hi: "एजेंट कक्ष" },
  heroKicker: { en: "Ask · Report · Get it done", hi: "पूछें · बताएँ · काम पूरा करें" },
  heroTitle: { en: "Government paperwork, done with you.", hi: "सरकारी कागज़ी काम, अब आपके साथ।" },
  heroBody: {
    en: "Find schemes you are eligible for, report a civic problem, and let our agent fill the portal. You only type the OTP, the CAPTCHA, and give the final yes.",
    hi: "अपनी पात्र योजनाएँ खोजें, नागरिक समस्या दर्ज करें, और हमारा एजेंट पोर्टल भर देगा। आपको केवल OTP, CAPTCHA और अंतिम मंज़ूरी देनी है।",
  },
  ctaSchemes: { en: "Find my schemes", hi: "मेरी योजनाएँ खोजें" },
  ctaReport: { en: "Report a problem", hi: "समस्या दर्ज करें" },
  watchAgent: { en: "Watch the agent", hi: "एजेंट को काम करते देखें" },
  bulletLive: { en: "Live government data", hi: "लाइव सरकारी डेटा" },
  bulletOtp: { en: "Your OTP stays with you", hi: "आपका OTP आपके पास रहता है" },
  bulletYes: { en: "Nothing filed without your yes", hi: "आपकी मंज़ूरी के बिना कुछ दर्ज नहीं होता" },
  howTitle: { en: "How it works", hi: "यह कैसे काम करता है" },
  pillarsTitle: { en: "Three ways we help", hi: "हम तीन तरह से मदद करते हैं" },
  liveTitle: { en: "Live right now", hi: "अभी लाइव" },
  trustTitle: { en: "Built to be trusted", hi: "भरोसे के लिए बनाया गया" },
  start: { en: "Start", hi: "शुरू करें" },
  disclaimer: {
    en: "Hackathon prototype · Not a Government of India website · Uses live public data from myScheme.gov.in, India Post and RBI IFSC records",
    hi: "हैकथॉन प्रोटोटाइप · यह भारत सरकार की वेबसाइट नहीं है · myScheme.gov.in, इंडिया पोस्ट और RBI IFSC का लाइव सार्वजनिक डेटा",
  },
} as const;

export type StringKey = keyof typeof STRINGS;

type Ctx = { lang: Lang; setLang: (l: Lang) => void; t: (k: StringKey) => string; scale: number; setScale: (s: number) => void };
const I18n = createContext<Ctx | null>(null);

function stored<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(() => stored("cp-lang", "en"));
  const [scale, setScale] = useState<number>(() => stored("cp-scale", 100));
  useEffect(() => {
    document.documentElement.lang = lang === "hi" ? "hi" : "en";
    document.documentElement.style.fontSize = `${scale}%`;
    try {
      localStorage.setItem("cp-lang", JSON.stringify(lang));
      localStorage.setItem("cp-scale", JSON.stringify(scale));
    } catch { /* private mode: settings just are not remembered */ }
  }, [lang, scale]);
  const t = (k: StringKey) => STRINGS[k][lang];
  return <I18n.Provider value={{ lang, setLang, t, scale, setScale }}>{children}</I18n.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18n);
  if (!ctx) throw new Error("useI18n outside provider");
  return ctx;
}
