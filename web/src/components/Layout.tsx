import { AnimatePresence, motion } from "motion/react";
import { AArrowDown, AArrowUp, Bot, ChevronDown, History, House, Languages, LogOut, Menu, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { authChangeEvent, clearAuthSession, getAuthSession, type AuthSession } from "../auth";
import { useI18n, type StringKey } from "../i18n";
import { Logo, TricolorStrip } from "./ui";

const PUBLIC_NAV: { to: string; key: StringKey }[] = [
  { to: "/", key: "navHome" },
  { to: "/schemes", key: "navSchemes" },
  { to: "/grievance", key: "navGrievance" },
  { to: "/board", key: "navBoard" },
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

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase() || "?";
}

/** Top-right account button: initials, then a menu with who is signed in, their pages, and Sign out. */
function AccountMenu({ session, dark, onSignOut }: { session: AuthSession; dark?: boolean; onSignOut: () => void }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const loc = useLocation();
  useEffect(() => { setOpen(false); }, [loc.pathname]);
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", esc); };
  }, [open]);
  const { user } = session;
  const admin = user.role === "admin";
  const item = "flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-semibold text-navy-800 hover:bg-navy-50";
  return (
    <div ref={box} className="relative">
      <button onClick={() => setOpen(!open)} aria-haspopup="menu" aria-expanded={open} aria-label={`Account: ${user.name}`}
        className={`flex min-h-10 items-center gap-2 rounded-full py-1 pl-1 pr-2 transition ${dark ? "hover:bg-white/10" : "hover:bg-navy-50"} ${open ? (dark ? "bg-white/10" : "bg-navy-50") : ""}`}>
        <span className="grid size-8 place-items-center rounded-full bg-gradient-to-br from-saffron-500 to-leaf-500 text-xs font-extrabold text-white ring-2 ring-white">{initials(user.name)}</span>
        <ChevronDown className={`size-4 transition-transform ${open ? "rotate-180" : ""} ${dark ? "text-slate-300" : "text-navy-700"}`} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div role="menu" initial={{ opacity: 0, y: -6, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.15 }}
            className="absolute right-0 top-full z-50 mt-2 w-72 rounded-2xl bg-white p-2 text-left shadow-2xl ring-1 ring-navy-100">
            <div className="flex items-center gap-3 rounded-xl bg-navy-50/70 p-3">
              <span className="grid size-11 shrink-0 place-items-center rounded-full bg-gradient-to-br from-saffron-500 to-leaf-500 text-sm font-extrabold text-white">{initials(user.name)}</span>
              <span className="min-w-0">
                <span className="block truncate font-bold text-navy-900">{user.name}</span>
                <span className="block truncate text-xs text-slate-600">{user.email}</span>
                <span className={`mt-1 inline-block rounded-full px-2 py-0.5 text-[11px] font-bold ${admin ? "bg-navy-700 text-white" : "bg-leaf-100 text-leaf-700"}`}>{admin ? "Municipal desk" : "Citizen"}</span>
              </span>
            </div>
            <div className="mt-1 grid">
              <Link role="menuitem" to={admin ? "/admin" : "/home"} className={item}><House className="size-4 text-navy-500" />{admin ? "Municipal desk" : "My home"}</Link>
              {!admin && <Link role="menuitem" to="/history" className={item}><History className="size-4 text-navy-500" />My history</Link>}
              {!admin && <Link role="menuitem" to="/agent/history" className={item}><Bot className="size-4 text-navy-500" />Agent runs</Link>}
              <button role="menuitem" onClick={onSignOut} className={`${item} text-red-700 hover:bg-red-50`}><LogOut className="size-4" />Sign out</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Header({ dark }: { dark?: boolean }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [session, setSession] = useState<AuthSession | null>(() => getAuthSession());
  const loc = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    const sync = () => setSession(getAuthSession());
    window.addEventListener(authChangeEvent, sync);
    window.addEventListener("storage", sync);
    return () => { window.removeEventListener(authChangeEvent, sync); window.removeEventListener("storage", sync); };
  }, []);
  useEffect(() => { setOpen(false); }, [loc.pathname]);
  const nav = useMemo(() => {
    if (!session) return PUBLIC_NAV;
    if (session.user.role === "admin") return [{ to: "/admin", key: "navAdmin" as StringKey }, { to: "/board", key: "navBoard" as StringKey }];
    return [{ to: "/home", key: "navHome" as StringKey }, ...PUBLIC_NAV.slice(1), { to: "/agent", key: "navAgent" as StringKey }];
  }, [session]);
  const active = (to: string) => (to === "/" ? loc.pathname === "/" : loc.pathname.startsWith(to) || (to === "/agent" && loc.pathname.startsWith("/citizen")));
  const home = session?.user.role === "citizen" ? "/home" : session?.user.role === "admin" ? "/admin" : "/";
  function signOut() { clearAuthSession(); navigate("/"); }
  return (
    <header className={`sticky top-0 z-40 ${dark ? "border-b border-white/5 bg-night-900/80 backdrop-blur" : "glass border-x-0 border-t-0"}`}>
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-2.5">
        <Link to={home} className="flex items-center gap-3" aria-label="Swayam-sevak home">
          <Logo size={dark ? 36 : 46} />
          <div className="leading-tight">
            <div className={`font-display text-xl font-extrabold ${dark ? "text-white" : "text-navy-900"}`}>Swayam-sevak <span className={`font-semibold ${dark ? "text-slate-400" : "text-saffron-700"}`}>· स्वयंसेवक</span></div>
            {!dark && <div className="text-xs font-medium text-slate-600">{t("brandTagline")}</div>}
          </div>
        </Link>
        <nav className="hidden items-center gap-1 lg:flex" aria-label="Main">
          {nav.map((n) => (
            <NavLink key={n.to} to={n.to} className={`relative rounded-lg px-3 py-2 text-sm font-semibold ${dark ? "text-slate-300 hover:text-white" : "text-navy-800 hover:bg-navy-50"}`}>
              {t(n.key)}
              {active(n.to) && <motion.span layoutId="nav-underline" className="absolute inset-x-2 -bottom-0.5 h-1 rounded-full tricolor-bar" />}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          {session ? <AccountMenu session={session} dark={dark} onSignOut={signOut} /> : <Link to="/signin" className={`hidden min-h-9 items-center rounded-lg px-3 text-sm font-bold lg:inline-flex ${dark ? "bg-white text-navy-900 hover:bg-navy-50" : "bg-navy-700 text-white hover:bg-navy-800"}`}>Sign in</Link>}
          <button className={`rounded-lg p-2 lg:hidden ${dark ? "text-white" : "text-navy-800"}`} aria-label="Menu" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button>
        </div>
      </div>
      <AnimatePresence>
        {open && (
          <motion.nav initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden lg:hidden" aria-label="Main mobile">
            <div className="flex flex-col gap-1 px-4 pb-3">
              {nav.map((n) => (
                <NavLink key={n.to} to={n.to} className={`rounded-xl px-3 py-3 font-semibold ${active(n.to) ? (dark ? "bg-white/10 text-white" : "bg-navy-50 text-navy-900") : dark ? "text-slate-300" : "text-navy-800"}`}>{t(n.key)}</NavLink>
              ))}
              {session && session.user.role === "citizen" && <NavLink to="/history" className={`rounded-xl px-3 py-3 font-semibold ${dark ? "text-slate-300" : "text-navy-800"}`}>My history</NavLink>}
              {session ? <button onClick={signOut} className={`rounded-xl px-3 py-3 text-left font-semibold ${dark ? "text-slate-300 hover:bg-white/10" : "text-navy-800 hover:bg-navy-50"}`}>Sign out</button> : <Link to="/signin" className={`rounded-xl px-3 py-3 font-semibold ${dark ? "text-white hover:bg-white/10" : "text-navy-800 hover:bg-navy-50"}`}>Sign in</Link>}
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
            <div className="font-display text-lg font-bold text-white">Swayam-sevak</div>
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
