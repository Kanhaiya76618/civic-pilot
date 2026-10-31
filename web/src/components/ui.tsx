import { animate, motion, useInView, useReducedMotion } from "motion/react";
import { CircleAlert, CircleCheck, LoaderCircle, ShieldAlert, X } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ComponentProps, type ReactNode } from "react";
import { PlugArt } from "./Illustrations";

/** Original Civic Pulse mark: saffron and green arcs around a navy pulse line. Not a government emblem. */
export function Logo({ size = 44, className = "" }: { size?: number; className?: string }) {
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} className={className} role="img" aria-label="Civic Pulse logo">
      <circle cx="32" cy="32" r="30" fill="#fff" />
      <path d="M8 30a24 24 0 0 1 48 0" fill="none" stroke="#FF9933" strokeWidth="6" strokeLinecap="round" />
      <path d="M56 36a24 24 0 0 1-48 0" fill="none" stroke="#138808" strokeWidth="6" strokeLinecap="round" />
      <path d="M12 33h10l5-10 7 20 5-12h13" fill="none" stroke="#13306B" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export const TricolorStrip = ({ className = "h-1.5" }: { className?: string }) => <div className={`tricolor-bar w-full ${className}`} aria-hidden />;

type BtnProps = ComponentProps<typeof motion.button> & { variant?: "primary" | "secondary" | "ghost" | "danger" | "saffron"; loading?: boolean };
export function Button({ variant = "primary", loading, className = "", children, disabled, ...p }: BtnProps) {
  const styles = {
    primary: "bg-navy-700 text-white hover:bg-navy-800 shadow-[0_8px_20px_-8px_rgb(19_48_107/0.6)]",
    saffron: "bg-saffron-500 text-navy-900 hover:bg-saffron-400 shadow-[0_8px_20px_-8px_rgb(255_153_51/0.7)]",
    secondary: "bg-white text-navy-700 ring-1 ring-navy-200 hover:ring-navy-400",
    ghost: "text-navy-700 hover:bg-navy-50",
    danger: "bg-red-600 text-white hover:bg-red-700",
  }[variant];
  return (
    <motion.button
      whileHover={{ y: -1 }}
      whileTap={{ scale: 0.97 }}
      transition={{ duration: 0.15 }}
      disabled={disabled || loading}
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-5 py-2.5 font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${className}`}
      {...p}
    >
      {loading && <LoaderCircle className="size-4 animate-spin" aria-hidden />}
      {children as ReactNode}
    </motion.button>
  );
}

export function Card({ variant = "glass", className = "", children, ...p }: ComponentProps<"div"> & { variant?: "glass" | "clay" | "plain" | "dark" }) {
  const v = { glass: "glass rounded-3xl", clay: "clay bg-white", plain: "rounded-3xl bg-white ring-1 ring-navy-100", dark: "glass-dark rounded-2xl text-slate-100" }[variant];
  return <div className={`${v} ${className}`} {...p}>{children}</div>;
}

export function Badge({ tone = "navy", children, className = "" }: { tone?: "navy" | "saffron" | "leaf" | "gray" | "red" | "blue"; children: ReactNode; className?: string }) {
  const t = {
    navy: "bg-navy-50 text-navy-700 ring-navy-200", saffron: "bg-saffron-50 text-saffron-700 ring-saffron-200",
    leaf: "bg-leaf-50 text-leaf-700 ring-leaf-200", gray: "bg-slate-100 text-slate-600 ring-slate-200",
    red: "bg-red-50 text-red-700 ring-red-200", blue: "bg-sky-50 text-sky-700 ring-sky-200",
  }[tone];
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${t} ${className}`}>{children}</span>;
}

const STATUS: Record<string, { label: string; tone: "navy" | "saffron" | "leaf" | "gray" | "red" | "blue" }> = {
  queued: { label: "Queued", tone: "gray" }, validating: { label: "Checking", tone: "blue" }, preparing_docs: { label: "Preparing documents", tone: "blue" },
  running: { label: "Working", tone: "blue" }, awaiting_human: { label: "Your turn", tone: "saffron" }, awaiting_approval: { label: "Needs your approval", tone: "saffron" },
  submitting: { label: "Submitting", tone: "navy" }, verifying: { label: "Verifying", tone: "navy" }, completed: { label: "Completed", tone: "leaf" },
  failed: { label: "Stopped", tone: "red" }, needs_review: { label: "Needs review", tone: "red" },
  planning: { label: "Planning", tone: "blue" }, out_of_scope: { label: "Out of scope", tone: "gray" }, stopped: { label: "Stopped", tone: "gray" },
  needs_details: { label: "Needs your details", tone: "saffron" }, handed_off: { label: "Handed to filing", tone: "navy" },
};
export function StatusBadge({ status }: { status: string }) {
  const s = STATUS[status] ?? { label: status, tone: "gray" as const };
  return <Badge tone={s.tone}>{["running", "planning", "validating", "preparing_docs", "submitting", "verifying"].includes(status) && <LoaderCircle className="size-3 animate-spin" aria-hidden />}{s.label}</Badge>;
}

/** Number that counts up when scrolled into view (instant with reduced motion). */
export function CountUp({ value, suffix = "", decimals = 0 }: { value: number; suffix?: string; decimals?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (!inView) return;
    if (reduce) { setShown(value); return; }
    const c = animate(0, value, { duration: 1.1, ease: "easeOut", onUpdate: setShown });
    return () => c.stop();
  }, [inView, value, reduce]);
  return <span ref={ref} className="tabular-nums">{shown.toFixed(decimals)}{suffix}</span>;
}

export function SectionTitle({ kicker, title, children }: { kicker?: string; title: string; children?: ReactNode }) {
  return (
    <div className="mb-8 max-w-2xl">
      {kicker && <p className="mb-2 text-sm font-bold uppercase tracking-[0.14em] text-saffron-700">{kicker}</p>}
      <h2 className="text-3xl font-extrabold text-navy-900 sm:text-4xl">{title}</h2>
      {children && <p className="mt-3 text-lg leading-relaxed text-slate-600">{children}</p>}
    </div>
  );
}

/** Honest empty state for a teammate's service that is not wired up yet: no placeholder data. */
export function NotConnected({ part, what, endpoint }: { part: string; what: string; endpoint: string }) {
  return (
    <Card variant="plain" className="flex flex-col items-center gap-3 p-8 text-center">
      <PlugArt className="h-24 w-auto" />
      <h3 className="text-xl font-bold text-navy-900">{part} is not connected yet</h3>
      <p className="max-w-md text-slate-600">{what}</p>
      <p className="text-sm text-slate-500">Set <code className="rounded bg-navy-50 px-1.5 py-0.5 font-mono text-navy-700">{endpoint}</code> on the server and this panel fills with live data.</p>
    </Card>
  );
}

// ---------------------------------------------------------------- toasts
type Toast = { id: number; tone: "ok" | "error" | "warn"; text: string };
const ToastCtx = createContext<(tone: Toast["tone"], text: string) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((tone: Toast["tone"], text: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, tone, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);
  const icon = { ok: <CircleCheck className="size-5 text-leaf-600" />, error: <CircleAlert className="size-5 text-red-600" />, warn: <ShieldAlert className="size-5 text-saffron-600" /> };
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[100] flex flex-col items-center gap-2 px-4" aria-live="polite">
        {toasts.map((t) => (
          <motion.div key={t.id} initial={{ opacity: 0, y: 20, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }}
            className="glass pointer-events-auto flex max-w-md items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium text-slate-800">
            {icon[t.tone]}<span className="flex-1">{t.text}</span>
            <button aria-label="Dismiss" className="rounded p-1 hover:bg-black/5" onClick={() => setToasts((x) => x.filter((y) => y.id !== t.id))}><X className="size-4" /></button>
          </motion.div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export const fadeUp = { hidden: { opacity: 0, y: 18 }, show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] as const } } };
export const stagger = { hidden: {}, show: { transition: { staggerChildren: 0.06 } } };
