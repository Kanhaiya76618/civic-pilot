import { AnimatePresence, motion } from "motion/react";
import {
  ArrowRight, Bookmark, BookmarkCheck, Bot, ExternalLink, FileText, Flame, Landmark, LoaderCircle, MapPin, Newspaper, RefreshCw,
  Search, Send, Sparkles, type LucideIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ago, me, type HistoryEntry, type HistoryKind, type News, type NewsItem } from "../api";
import { useToast } from "./ui";

export const KINDS: Record<HistoryKind, { label: string; icon: LucideIcon; tint: string }> = {
  explain: { label: "Explained", icon: FileText, tint: "bg-leaf-50 text-leaf-700 ring-leaf-200" },
  agent: { label: "Agent", icon: Bot, tint: "bg-navy-50 text-navy-700 ring-navy-200" },
  lookup: { label: "Scheme lookup", icon: Search, tint: "bg-saffron-50 text-saffron-700 ring-saffron-200" },
  filing: { label: "Filing", icon: Send, tint: "bg-navy-50 text-navy-700 ring-navy-200" },
  report: { label: "Report", icon: MapPin, tint: "bg-saffron-50 text-saffron-700 ring-saffron-200" },
  news: { label: "Saved news", icon: Bookmark, tint: "bg-slate-100 text-slate-700 ring-slate-200" },
};

/** Explainable means the Part 1 explainer accepts the link: an official .gov.in / .nic.in page. */
const explainable = (url: string) => /^https:\/\/([\w-]+\.)*(gov|nic)\.in\//.test(url);

function NewsRow({ it, saved, onSave }: { it: NewsItem; saved: boolean; onSave?: (it: NewsItem) => void }) {
  return (
    <motion.li layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}
      className="group grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-3 rounded-2xl p-3 transition hover:bg-navy-50/60">
      <span className={`mt-0.5 grid size-9 place-items-center rounded-xl ring-1 ${it.official ? "bg-saffron-50 text-saffron-700 ring-saffron-200" : "bg-white text-navy-600 ring-navy-100"}`}>
        {it.official ? <Landmark className="size-4" /> : <Newspaper className="size-4" />}
      </span>
      <div className="min-w-0">
        <a href={it.url} target="_blank" rel="noopener noreferrer" lang={it.lang}
          className="font-semibold leading-snug text-navy-900 underline-offset-2 hover:text-navy-700 hover:underline">{it.title}</a>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500">
          <span className="font-semibold text-slate-600">{it.source}</span>
          {it.published && <><span aria-hidden>·</span><time dateTime={it.published}>{ago(it.published)}</time></>}
          {it.official && <span className="rounded-full bg-saffron-50 px-2 py-0.5 font-bold text-saffron-700 ring-1 ring-saffron-200">Official</span>}
          {explainable(it.url) && (
            <Link to={`/schemes?url=${encodeURIComponent(it.url)}`} className="inline-flex items-center gap-1 rounded-full bg-leaf-50 px-2 py-0.5 font-bold text-leaf-700 ring-1 ring-leaf-200 hover:bg-leaf-100">
              <Sparkles className="size-3" />Explain this
            </Link>
          )}
        </div>
      </div>
      {onSave ? <button onClick={() => onSave(it)} disabled={saved} aria-label={saved ? "Saved to your history" : `Save: ${it.title}`}
        className={`grid size-9 place-items-center rounded-xl transition ${saved ? "text-leaf-600" : "text-slate-400 hover:bg-white hover:text-navy-700"}`}>
        {saved ? <BookmarkCheck className="size-5" /> : <Bookmark className="size-5" />}
      </button> : <span />}
    </motion.li>
  );
}

/** Live headlines on schemes, rights, civic issues and digital services (Google News + PIB), refreshed by the server. */
export function NewsPanel({ trendingOut, canSave = true }: { trendingOut?: (t: News["trending"], pick: (term: string) => void) => void; canSave?: boolean }) {
  const toast = useToast();
  const [news, setNews] = useState<News | null>(null);
  const [error, setError] = useState(false);
  const [topic, setTopic] = useState("all");
  const [term, setTerm] = useState("");
  const [query, setQuery] = useState("");
  const [shown, setShown] = useState(8);
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState<Set<string>>(new Set());

  const load = (refresh = false) => {
    setLoading(true);
    me.news(refresh).then((n) => { setNews(n); setError(false); }).catch(() => setError(true)).finally(() => setLoading(false));
  };
  useEffect(() => { load(); const t = window.setInterval(() => load(), 10 * 60 * 1000); return () => clearInterval(t); }, []);
  useEffect(() => { if (canSave) me.history("news").then((h) => setSaved(new Set(h.map((x) => x.link ?? "")))).catch(() => {}); }, [canSave]);
  useEffect(() => { if (news) trendingOut?.(news.trending, (t) => { setTerm(t); setTopic("all"); setShown(8); }); }, [news]); // eslint-disable-line react-hooks/exhaustive-deps

  const items = useMemo(() => {
    const q = (term || query).trim().toLowerCase();
    return (news?.items ?? []).filter((it) => (topic === "all" || it.topic === topic) && (!q || it.title.toLowerCase().includes(q)));
  }, [news, topic, term, query]);

  async function save(it: NewsItem) {
    try {
      await me.add({ kind: "news", title: it.title, subtitle: it.source, link: it.url, meta: { topic: it.topic, published: it.published } });
      setSaved((s) => new Set(s).add(it.url));
      toast("ok", "Saved to your history");
    } catch (e) { toast("error", (e as Error).message); }
  }

  return (
    <section className="flex h-full flex-col rounded-3xl bg-white p-5 shadow-[0_18px_44px_-30px_rgb(19_48_107/.45)] ring-1 ring-navy-100 sm:p-6" aria-labelledby="news-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.14em] text-saffron-700">
            <span className="relative flex size-2"><span className="absolute inline-flex size-full animate-ping rounded-full bg-red-500 opacity-60" /><span className="relative inline-flex size-2 rounded-full bg-red-500" /></span>Live
          </p>
          <h2 id="news-title" className="mt-1 text-2xl font-extrabold text-navy-900">Schemes, rights and civic news</h2>
          <p className="mt-1 text-sm text-slate-500">
            {news ? <>Updated {ago(news.updated_at)}{news.stale && " (sources unreachable: showing the last headlines)"} · {news.items.length} headlines from {news.sources.length} feeds</> : "Loading the latest headlines…"}
          </p>
        </div>
        <button onClick={() => load(true)} disabled={loading} className="inline-flex min-h-10 items-center gap-2 rounded-xl px-3 text-sm font-semibold text-navy-700 ring-1 ring-navy-100 hover:bg-navy-50 disabled:opacity-60">
          <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />Refresh
        </button>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="News topics">
          {[{ id: "all", label: "All" }, ...(news?.topics ?? [])].map((t) => (
            <button key={t.id} role="tab" aria-selected={topic === t.id} onClick={() => { setTopic(t.id); setShown(8); }}
              className={`relative min-h-9 rounded-full px-3 text-sm font-semibold transition ${topic === t.id ? "text-white" : "text-navy-700 ring-1 ring-navy-100 hover:bg-navy-50"}`}>
              {topic === t.id && <motion.span layoutId="news-topic" className="absolute inset-0 rounded-full bg-navy-700" transition={{ type: "spring", stiffness: 400, damping: 32 }} />}
              <span className="relative">{t.label}</span>
            </button>
          ))}
        </div>
        <label className="ml-auto flex min-h-9 items-center gap-2 rounded-full px-3 ring-1 ring-navy-100 focus-within:ring-2 focus-within:ring-navy-300">
          <Search className="size-4 text-slate-400" aria-hidden />
          <span className="sr-only">Search headlines</span>
          <input value={query} onChange={(e) => { setQuery(e.target.value); setTerm(""); }} placeholder="Search headlines" className="w-36 bg-transparent text-sm outline-none" />
        </label>
      </div>
      {term && (
        <p className="mt-3 inline-flex w-fit items-center gap-2 rounded-full bg-saffron-50 px-3 py-1 text-sm font-semibold text-saffron-800 ring-1 ring-saffron-200">
          <Flame className="size-4" />Trending: {term}<button onClick={() => setTerm("")} className="ml-1 text-saffron-700 hover:text-saffron-900" aria-label="Clear trending filter">×</button>
        </p>
      )}

      <div className="mt-3 flex-1">
        {error && !news && <p className="rounded-2xl bg-red-50 p-4 text-sm text-red-700">The news feeds could not be reached. Try Refresh in a moment.</p>}
        {!news && !error && <ul className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <li key={i} className="h-16 animate-pulse rounded-2xl bg-navy-50/70" />)}</ul>}
        {news && items.length === 0 && <p className="rounded-2xl bg-navy-50/60 p-4 text-sm text-slate-600">No headlines match. Try another topic.</p>}
        <ul className="-mx-1 divide-y divide-navy-50">
          <AnimatePresence initial={false}>
            {items.slice(0, shown).map((it) => <NewsRow key={it.url} it={it} saved={saved.has(it.url)} onSave={canSave ? save : undefined} />)}
          </AnimatePresence>
        </ul>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-navy-50 pt-3 text-xs text-slate-500">
        <span>Headlines from Google News and PIB, linked to the original. Not verified by Swayam-sevak.</span>
        {items.length > shown && (
          <button onClick={() => setShown((n) => n + 8)} className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-sm font-bold text-navy-700 hover:bg-navy-50">
            Show more ({items.length - shown})<ArrowRight className="size-4" />
          </button>
        )}
      </div>
    </section>
  );
}

export function HistoryRow({ h, onDelete, compact }: { h: HistoryEntry; onDelete?: (h: HistoryEntry) => void; compact?: boolean }) {
  const k = KINDS[h.kind];
  const external = h.link?.startsWith("https://");
  const body = (
    <>
      <span className={`grid size-9 shrink-0 place-items-center rounded-xl ring-1 ${k.tint}`}><k.icon className="size-4" /></span>
      <span className="min-w-0 flex-1">
        <span className={`block font-semibold text-navy-900 ${compact ? "truncate text-sm" : "leading-snug"}`}>{h.title}</span>
        <span className="block truncate text-xs text-slate-500">{k.label}{h.subtitle ? ` · ${h.subtitle}` : ""} · {ago(h.created_at)}</span>
      </span>
      {h.link && (external ? <ExternalLink className="size-4 shrink-0 text-slate-400" /> : <ArrowRight className="size-4 shrink-0 text-slate-400" />)}
    </>
  );
  const cls = "flex min-w-0 flex-1 items-center gap-3 rounded-xl p-2 text-left transition hover:bg-navy-50/70";
  return (
    <motion.li layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, height: 0 }} className="flex items-center gap-1">
      {!h.link ? <div className={cls}>{body}</div> : external
        ? <a href={h.link} target="_blank" rel="noopener noreferrer" className={cls}>{body}</a>
        : <Link to={h.link} className={cls}>{body}</Link>}
      {onDelete && <button onClick={() => onDelete(h)} aria-label={`Remove ${h.title}`} className="grid size-9 shrink-0 place-items-center rounded-xl text-slate-400 hover:bg-red-50 hover:text-red-600">×</button>}
    </motion.li>
  );
}

export function RecentActivity() {
  const [items, setItems] = useState<HistoryEntry[] | null>(null);
  useEffect(() => { me.history().then((h) => setItems(h.slice(0, 6))).catch(() => setItems([])); }, []);
  return (
    <section className="rounded-3xl bg-white p-5 shadow-[0_18px_44px_-30px_rgb(19_48_107/.45)] ring-1 ring-navy-100" aria-labelledby="recent-title">
      <div className="flex items-center justify-between">
        <h2 id="recent-title" className="text-lg font-extrabold text-navy-900">Your recent activity</h2>
        <Link to="/history" className="inline-flex items-center gap-1 text-sm font-bold text-navy-700 hover:text-saffron-700">All<ArrowRight className="size-4" /></Link>
      </div>
      {items === null && <p className="mt-4 flex items-center gap-2 text-sm text-slate-500"><LoaderCircle className="size-4 animate-spin" />Loading…</p>}
      {items?.length === 0 && (
        <p className="mt-3 rounded-2xl bg-navy-50/60 p-4 text-sm leading-relaxed text-slate-600">
          Nothing yet. Explanations, agent runs, filings and saved news appear here, so you can come back to them.
        </p>
      )}
      <ul className="mt-2 space-y-0.5">{items?.map((h) => <HistoryRow key={h.id} h={h} compact />)}</ul>
    </section>
  );
}
