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
  navAdmin: { en: "Municipal Desk", hi: "नगरपालिका डेस्क" },
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
  homeSearchLabel: { en: "Ask a question about a scheme", hi: "किसी योजना के बारे में पूछें" },
  homeSearchPlaceholder: { en: "Ask about a scholarship, pension, housing or farming scheme", hi: "छात्रवृत्ति, पेंशन, आवास या खेती की योजना के बारे में पूछें" },
  homeAsk: { en: "Ask now", hi: "अभी पूछें" },
  homeSpeak: { en: "Speak your question", hi: "अपना प्रश्न बोलें" },
  homeStopListening: { en: "Stop listening", hi: "सुनना बंद करें" },
  languageEnglish: { en: "English", hi: "अंग्रेज़ी" },
  languageHindi: { en: "हिन्दी", hi: "हिन्दी" },
  languageTamil: { en: "தமிழ்", hi: "तमिल" },
  languageBengali: { en: "বাংলা", hi: "बंगाली" },
  languageMarathi: { en: "मराठी", hi: "मराठी" },
  languageTelugu: { en: "తెలుగు", hi: "तेलुगु" },
  homeTrustTasks: { en: "Live tasks started", hi: "लाइव कार्य शुरू हुए" },
  homeTrustFilings: { en: "Filed with approval", hi: "मंज़ूरी से दर्ज हुए" },
  homeTrustReceipts: { en: "Signed receipts", hi: "हस्ताक्षरित रसीदें" },
  homeCategoryKicker: { en: "Start with what matters to you", hi: "अपनी ज़रूरत से शुरुआत करें" },
  homeCategoryTitle: { en: "Browse by category", hi: "श्रेणी के अनुसार देखें" },
  homeCategoryBody: { en: "Choose a need and we will take you to a live, source-backed check before you apply.", hi: "अपनी ज़रूरत चुनें; आवेदन से पहले हम आपको लाइव, स्रोत-आधारित जाँच तक ले जाएँगे।" },
  categoryEducation: { en: "Education", hi: "शिक्षा" },
  categoryEducationBody: { en: "Scholarships, fee support and study assistance.", hi: "छात्रवृत्ति, फीस सहायता और पढ़ाई का सहयोग।" },
  categoryFarming: { en: "Farming", hi: "कृषि" },
  categoryFarmingBody: { en: "Support for crops, equipment and rural livelihoods.", hi: "फसल, उपकरण और ग्रामीण आजीविका के लिए सहायता।" },
  categoryHousing: { en: "Housing", hi: "आवास" },
  categoryHousingBody: { en: "Housing support and services for your household.", hi: "आपके परिवार के लिए आवास सहायता और सेवाएँ।" },
  categoryHealth: { en: "Health", hi: "स्वास्थ्य" },
  categoryHealthBody: { en: "Care, insurance and family health support.", hi: "देखभाल, बीमा और परिवार स्वास्थ्य सहायता।" },
  categoryBusiness: { en: "Small business", hi: "लघु व्यवसाय" },
  categoryBusinessBody: { en: "Loans, skills and support for local enterprises.", hi: "ऋण, कौशल और स्थानीय उद्यमों का सहयोग।" },
  categoryEmployment: { en: "Employment", hi: "रोज़गार" },
  categoryEmploymentBody: { en: "Skills, job support and worker benefits.", hi: "कौशल, नौकरी सहायता और श्रमिक लाभ।" },
  homeDeadline: { en: "Check official deadline", hi: "आधिकारिक अंतिम तिथि देखें" },
  homeEligibility: { en: "Check eligibility", hi: "पात्रता जाँचें" },
  homeApply: { en: "Apply now", hi: "अभी आवेदन करें" },
  homeEligibilityKicker: { en: "Before the paperwork", hi: "कागज़ी काम से पहले" },
  homeEligibilityTitle: { en: "Check your eligibility in 3 steps", hi: "3 चरणों में अपनी पात्रता जाँचें" },
  homeEligibilityBody: { en: "Answer only what is needed. The live scheme finder confirms results from the official portal.", hi: "केवल ज़रूरी जानकारी दें। लाइव योजना खोजक आधिकारिक पोर्टल से परिणाम की पुष्टि करता है।" },
  homeStepNeed: { en: "What do you need?", hi: "आपको क्या चाहिए?" },
  homeStepDetails: { en: "Your details", hi: "आपकी जानकारी" },
  homeStepResult: { en: "Eligibility", hi: "पात्रता" },
  homeChooseCategory: { en: "Choose one area to begin", hi: "शुरू करने के लिए एक क्षेत्र चुनें" },
  homeContinue: { en: "Continue", hi: "आगे बढ़ें" },
  homeBack: { en: "Back", hi: "वापस" },
  homeAge: { en: "Age", hi: "उम्र" },
  homeIncome: { en: "Annual household income", hi: "वार्षिक पारिवारिक आय" },
  homeState: { en: "State", hi: "राज्य" },
  homeChooseState: { en: "Choose your state", hi: "अपना राज्य चुनें" },
  stateKarnataka: { en: "Karnataka", hi: "कर्नाटक" },
  stateMaharashtra: { en: "Maharashtra", hi: "महाराष्ट्र" },
  stateDelhi: { en: "Delhi", hi: "दिल्ली" },
  stateOther: { en: "Another state", hi: "अन्य राज्य" },
  homeReadyTitle: { en: "Ready for a live eligibility check", hi: "लाइव पात्रता जाँच के लिए तैयार" },
  homeReadyBody: { en: "We will use your answers to guide the official myScheme questionnaire. The portal’s result—not a guessed answer—determines what you can apply for.", hi: "हम आपके उत्तरों से आधिकारिक myScheme प्रश्नावली तक पहुँचेंगे। पोर्टल का परिणाम—अनुमान नहीं—तय करेगा कि आप किन योजनाओं के लिए आवेदन कर सकते हैं।" },
  homeFindSchemes: { en: "Find my schemes", hi: "मेरी योजनाएँ खोजें" },
  homeTakesTwoMinutes: { en: "Takes under 2 minutes", hi: "2 मिनट से कम समय" },
  homeNoDocs: { en: "No documents needed to start", hi: "शुरू करने के लिए दस्तावेज़ नहीं चाहिए" },
  homePrivateDetails: { en: "Private details stay protected", hi: "निजी जानकारी सुरक्षित रहती है" },
  homeAskLanguage: { en: "Confused? Ask in your language.", hi: "उलझन है? अपनी भाषा में पूछें।" },
  homeEligibilityArt: { en: "Citizen answering a government scheme questionnaire on a phone", hi: "फोन पर सरकारी योजना प्रश्नावली का उत्तर देता नागरिक" },
  homeHowKicker: { en: "Simple, step by step", hi: "सरल, चरण-दर-चरण" },
  homeHowAsk: { en: "Ask in your language", hi: "अपनी भाषा में पूछें" },
  homeHowAskBody: { en: "Start with a question or choose a service.", hi: "एक प्रश्न से शुरू करें या सेवा चुनें।" },
  homeHowCheck: { en: "Check eligibility", hi: "पात्रता जाँचें" },
  homeHowCheckBody: { en: "Use the official portal’s own questions.", hi: "आधिकारिक पोर्टल के अपने प्रश्नों का उपयोग करें।" },
  homeHowApply: { en: "Agent applies with you", hi: "एजेंट आपके साथ आवेदन करता है" },
  homeHowApplyBody: { en: "Watch each step and take over for OTPs.", hi: "हर चरण देखें और OTP के लिए खुद संभालें।" },
  homeHowTrack: { en: "Keep the receipt", hi: "रसीद सुरक्षित रखें" },
  homeHowTrackBody: { en: "Verify the signed record whenever you need it.", hi: "जब चाहें हस्ताक्षरित रिकॉर्ड सत्यापित करें।" },
  homeAccountabilityTitle: { en: "Every application, clearly tracked.", hi: "हर आवेदन का स्पष्ट रिकॉर्ड।" },
  homeAccountabilityBody: { en: "View live, privacy-preserving task outcomes and signed receipts from this server.", hi: "इस सर्वर से लाइव, गोपनीयता-सुरक्षित कार्य परिणाम और हस्ताक्षरित रसीदें देखें।" },
  homeViewBoard: { en: "View accountability board", hi: "जवाबदेही बोर्ड देखें" },
  homeTasksStarted: { en: "Tasks started", hi: "कार्य शुरू हुए" },
  homeCompleted: { en: "Completed", hi: "पूर्ण हुए" },
  homeFiled: { en: "Filed with approval", hi: "मंज़ूरी से दर्ज हुए" },
  homeMedian: { en: "Median live lookup", hi: "मध्य लाइव खोज" },
  homeOpenAgent: { en: "Open the agent room", hi: "एजेंट कक्ष खोलें" },
  homePillarBody1: { en: "Ask in your language. See which schemes you can get, with the official source, and listen to the answer.", hi: "अपनी भाषा में पूछें। आधिकारिक स्रोत के साथ जानें कि आपको कौन-सी योजनाएँ मिल सकती हैं।" },
  homePillarBody2: { en: "Photograph a civic problem. We locate it, sort it, and show its progress publicly.", hi: "नागरिक समस्या की तस्वीर लें। हम उसे पहचानते, व्यवस्थित करते और उसकी प्रगति सार्वजनिक रूप से दिखाते हैं।" },
  homePillarBody3: { en: "The agent fills a government portal in a real browser. You type the OTP and approve before anything is submitted.", hi: "एजेंट असली ब्राउज़र में सरकारी पोर्टल भरता है। आप OTP टाइप करते हैं और जमा होने से पहले मंज़ूरी देते हैं।" },
  homePart1: { en: "Part 1", hi: "भाग 1" },
  homePart2: { en: "Part 2", hi: "भाग 2" },
  homePart3: { en: "Part 3", hi: "भाग 3" },
  homeGetItDone: { en: "Get it done", hi: "काम पूरा करें" },
  homeTrustConsent: { en: "Your consent first", hi: "पहले आपकी मंज़ूरी" },
  homeTrustConsentBody: { en: "Every task starts with explicit consent, limited to one portal and 24 hours.", hi: "हर कार्य स्पष्ट मंज़ूरी से शुरू होता है, एक पोर्टल और 24 घंटे तक सीमित।" },
  homeTrustPrivate: { en: "Private stays private", hi: "निजी जानकारी निजी रहती है" },
  homeTrustPrivateBody: { en: "Bank, phone and email are encrypted. The AI only sees placeholders.", hi: "बैंक, फोन और ईमेल एन्क्रिप्टेड रहते हैं। AI केवल प्लेसहोल्डर देखता है।" },
  homeTrustKeys: { en: "You hold the keys", hi: "नियंत्रण आपके पास है" },
  homeTrustKeysBody: { en: "You type OTPs and CAPTCHAs yourself. Nothing is filed without your approval.", hi: "आप OTP और CAPTCHA स्वयं टाइप करते हैं। आपकी मंज़ूरी के बिना कुछ दर्ज नहीं होता।" },
  homeTrustProof: { en: "Proof you can check", hi: "ऐसा प्रमाण जिसे आप जाँच सकते हैं" },
  homeTrustProofBody: { en: "Receipts are signed, so you can check they were not changed later.", hi: "रसीदें हस्ताक्षरित होती हैं, ताकि आप जाँच सकें कि बाद में उनमें बदलाव नहीं हुआ।" },
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
