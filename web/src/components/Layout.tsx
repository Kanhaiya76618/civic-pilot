import { AnimatePresence, motion } from "motion/react";
import { AArrowDown, AArrowUp, Languages, Menu, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useI18n, type StringKey } from "../i18n";
import { Logo, TricolorStrip } from "./ui";

const NAV: { to: string; key: StringKey }[] = [
  { to: "/", key: "navHome" },
  { to: "/schemes", key: "navSchemes" },
  { to: "/grievance", key: "navGrievance" },
  { to: "/board", key: "navBoard" },
  { to: "/agent", key: "navAgent" },
];

function UtilityBar({ dark }: { dark?: boolean }) {
  const { t, lang, setLang, scale, setScale } = useI18n();
  const btn = `inline-flex min-h-8 min-w-8 items-center justify-center rounded-md px-2 text-xs font-semibold ${dark ? "text-slate-300 hover:bg-white/10" : "text-navy-700 hover:bg-navy-50"}`;
  return (
    <div className={dark ? "bg-night-900 text-slate-300" : "bg-navy-800 text-white"}>
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-2 px-4 py-1 text-xs">
        <a href="#main" className="rounded px-2 py-1 font-medium underline-offset-2 hover:underline focus:not-sr-only">{t("skip")}</a>
        <div className="flex items-center gap-1">
          <span className="hidden sm:inline opacity-80">{t("textSize")}</span>
          <div className={`flex items-center rounded-lg ${dark ? "bg-white/5" : "bg-white"}`}>
            <button className={btn} aria-label="Smaller text" onClick={() => setScale(Math.max(87.5, scale - 12.5))}><AArrowDown className="size-4" /></button>
            <button className={btn} aria-label="Default text size" onClick={() => setScale(100)}>A</button>
            <button className={btn} aria-label="Larger text" onClick={() => setScale(Math.min(125, scale + 12.5))}><AArrowUp className="size-4" /></button>
          </div>
          <button
            className={`ml-1 inline-flex min-h-8 items-center gap-1 rounded-lg px-2.5 font-semibold ${dark ? "bg-white/5 hover:bg-white/10" : "bg-white text-navy-700 hover:bg-navy-50"}`}
            onClick={() => setLang(lang === "en" ? "hi" : "en")}
            aria-label={lang === "en" ? "हिन्दी में देखें" : "View in English"}
          >
            <Languages className="size-4" />{lang === "en" ? "हिन्दी" : "English"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Header({ dark }: { dark?: boolean }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => { setOpen(false); }, [loc.pathname]);
  const active = (to: string) => (to === "/" ? loc.pathname === "/" : loc.pathname.startsWith(to) || (to === "/agent" && loc.pathname.startsWith("/citizen")));
  return (
    <header className={`sticky top-0 z-40 ${dark ? "border-b border-white/5 bg-night-900/80 backdrop-blur" : "glass border-x-0 border-t-0"}`}>
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-2.5">
        <Link to="/" className="flex items-center gap-3" aria-label="Civic Pulse home">
          <Logo size={dark ? 36 : 46} />
          <div className="leading-tight">
            <div className={`font-display text-xl font-extrabold ${dark ? "text-white" : "text-navy-900"}`}>Civic Pulse <span className={`font-semibold ${dark ? "text-slate-400" : "text-saffron-700"}`}>· सिविक पल्स</span></div>
            {!dark && <div className="text-xs font-medium text-slate-600">{t("brandTagline")}</div>}
          </div>
        </Link>
        <nav className="hidden items-center gap-1 lg:flex" aria-label="Main">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} className={`relative rounded-lg px-3 py-2 text-sm font-semibold ${dark ? "text-slate-300 hover:text-white" : "text-navy-800 hover:bg-navy-50"}`}>
              {t(n.key)}
              {active(n.to) && <motion.span layoutId="nav-underline" className="absolute inset-x-2 -bottom-0.5 h-1 rounded-full tricolor-bar" />}
            </NavLink>
          ))}
        </nav>
        <button className={`rounded-lg p-2 lg:hidden ${dark ? "text-white" : "text-navy-800"}`} aria-label="Menu" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? <X /> : <Menu />}
        </button>
      </div>
      <AnimatePresence>
        {open && (
          <motion.nav initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden lg:hidden" aria-label="Main mobile">
            <div className="flex flex-col gap-1 px-4 pb-3">
              {NAV.map((n) => (
                <NavLink key={n.to} to={n.to} className={`rounded-xl px-3 py-3 font-semibold ${active(n.to) ? (dark ? "bg-white/10 text-white" : "bg-navy-50 text-navy-900") : dark ? "text-slate-300" : "text-navy-800"}`}>{t(n.key)}</NavLink>
              ))}
            </div>
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
  );
}

function Footer({ dark }: { dark?: boolean }) {
  const { t } = useI18n();
  return (
    <footer className={dark ? "border-t border-white/5 bg-night-950 text-slate-400" : "mt-20 bg-navy-900 text-navy-100"}>
      <TricolorStrip className="h-1" />
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:grid-cols-3">
        <div className="flex items-start gap-3">
          <Logo size={40} />
          <div>
            <div className="font-display text-lg font-bold text-white">Civic Pulse</div>
            <p className="mt-1 text-sm opacity-80">Assisted filing: a human approves every submission.</p>
          </div>
        </div>
        <div className="text-sm">
          <div className="mb-2 font-semibold text-white">Live data sources</div>
          <ul className="space-y-1 opacity-85">
            <li><a className="underline-offset-2 hover:underline" href="https://www.myscheme.gov.in" target="_blank" rel="noopener noreferrer">myScheme.gov.in</a> (scheme results, read live)</li>
            <li>India Post PIN code data (api.postalpincode.in)</li>
            <li>RBI IFSC data (ifsc.razorpay.com)</li>
          </ul>
        </div>
        <div className="text-sm">
          <div className="mb-2 font-semibold text-white">Your data</div>
          <p className="opacity-85">Private fields are encrypted and never shown to the AI. OTPs and CAPTCHAs are typed by you, not stored.</p>
        </div>
      </div>
      <div className={`px-4 py-3 text-center text-xs font-medium ${dark ? "bg-night-900" : "bg-navy-800 text-white"}`}>{t("disclaimer")}</div>
    </footer>
  );
}

export function Layout({ children, dark = false }: { children: ReactNode; dark?: boolean }) {
  const loc = useLocation();
  return (
    <div className={`flex min-h-dvh flex-col ${dark ? "bg-night text-slate-100" : "bg-civic"}`}>
      <TricolorStrip />
      <UtilityBar dark={dark} />
      <Header dark={dark} />
      <motion.main
        id="main"
        key={loc.pathname}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
        className="flex-1"
      >
        {children}
      </motion.main>
      <Footer dark={dark} />
    </div>
  );
}
