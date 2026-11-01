import { motion } from "motion/react";
import { ArrowRight, Bot, FileSearch, Flame, Hand, KeyRound, Map, MapPinned, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { me, type HistoryEntry, type News } from "../api";
import { getAuthSession } from "../auth";
import { NewsPanel, RecentActivity } from "../components/HomeWidgets";
import { CivicGuideChat } from "../components/CivicGuideChat";
import { fadeUp, stagger } from "../components/ui";

const ACTIONS = [
  { icon: FileSearch, title: "Explain a notice", body: "Rights, eligibility and impact, in your language, with a voice.", to: "/schemes", tint: "bg-leaf-50 text-leaf-700 ring-leaf-200" },
  { icon: MapPinned, title: "Report a problem", body: "Photo, location and the right department, filed with your approval.", to: "/grievance", tint: "bg-saffron-50 text-saffron-700 ring-saffron-200" },
  { icon: Bot, title: "Ask the agent", body: "It searches official sites and works the portal while you watch.", to: "/agent", tint: "bg-navy-50 text-navy-700 ring-navy-200" },
  { icon: Map, title: "Accountability board", body: "See reported issues and how they are being handled.", to: "/board", tint: "bg-slate-100 text-slate-700 ring-slate-200" },
];

const card = "rounded-3xl bg-white shadow-[0_18px_44px_-30px_rgb(19_48_107/.45)] ring-1 ring-navy-100";

export default function CitizenHome() {
  const session = getAuthSession();
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [historyReady, setHistoryReady] = useState(false);
  const [trend, setTrend] = useState<{ terms: News["trending"]; pick: (t: string) => void } | null>(null);
  useEffect(() => {
    if (!session) return;
    me.history().then(setHistory).catch(() => {}).finally(() => setHistoryReady(true));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const counts = useMemo(() => ({
    completed: history.filter((h) => ["explain", "lookup", "filing", "report", "agent"].includes(h.kind)).length,
    saved: history.filter((h) => h.kind === "news").length,
    week: history.filter((h) => Date.now() - new Date(h.created_at).getTime() < 7 * 864e5).length,
  }), [history]);
  if (!session || session.user.role !== "citizen") return <Navigate to="/signin?role=citizen" replace />;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:py-10">
      <CivicGuideChat activity={historyReady ? { completed: counts.completed, week: counts.week, saved: counts.saved } : null} />

      {/* 2. Actions: four equal tiles */}
      <motion.section initial="hidden" animate="show" variants={stagger} className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Start something">
        {ACTIONS.map((a) => (
          <motion.div key={a.title} variants={fadeUp} whileHover={{ y: -3 }}>
            <Link to={a.to} className={`group flex h-full flex-col p-5 ${card} transition hover:ring-navy-300`}>
              <span className={`grid size-11 place-items-center rounded-2xl ring-1 ${a.tint}`}><a.icon className="size-5" /></span>
              <h2 className="mt-4 text-lg font-extrabold text-navy-900">{a.title}</h2>
              <p className="mt-1 flex-1 text-sm leading-6 text-slate-600">{a.body}</p>
              <span className="mt-4 inline-flex items-center gap-1 text-sm font-bold text-navy-700">Start<ArrowRight className="size-4 transition group-hover:translate-x-1" /></span>
            </Link>
          </motion.div>
        ))}
      </motion.section>

      {/* 3. News (8 columns) beside activity and trending (4 columns) */}
      <section className="mt-6 grid gap-6 lg:grid-cols-12">
        <div className="min-w-0 lg:col-span-8">
          <NewsPanel trendingOut={(terms, pick) => setTrend({ terms, pick })} />
        </div>
        {/* min-w-0 and minmax(0,1fr): long one-line titles must shrink with the column, not widen the page */}
        <aside className="grid min-w-0 grid-cols-[minmax(0,1fr)] content-start gap-6 lg:col-span-4">
          <RecentActivity />
          <section className={`${card} p-5`} aria-labelledby="trend-title">
            <h2 id="trend-title" className="flex items-center gap-2 text-lg font-extrabold text-navy-900"><Flame className="size-5 text-saffron-600" />Trending in the news</h2>
            <p className="mt-1 text-xs text-slate-500">Most mentioned in the current headlines. Tap one to filter.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {!trend && <span className="h-8 w-40 animate-pulse rounded-full bg-navy-50" />}
              {trend?.terms.length === 0 && <span className="text-sm text-slate-500">Nothing stands out right now.</span>}
              {trend?.terms.map((t) => (
                <button key={t.term} onClick={() => { trend.pick(t.term); document.getElementById("news-title")?.scrollIntoView({ behavior: "smooth", block: "start" }); }}
                  className="inline-flex min-h-8 items-center gap-1.5 rounded-full bg-saffron-50 px-3 text-sm font-semibold text-saffron-800 ring-1 ring-saffron-200 hover:bg-saffron-100">
                  {t.term}<span className="rounded-full bg-white px-1.5 text-xs text-saffron-700">{t.count}</span>
                </button>
              ))}
            </div>
          </section>
        </aside>
      </section>

      {/* 4. Control */}
      <section className="mt-6 grid gap-4 rounded-3xl bg-navy-900 p-5 text-white sm:grid-cols-3 sm:p-6" aria-label="You stay in control">
        {[
          { icon: ShieldCheck, t: "Nothing filed without your yes", b: "Final Submit waits for your approval." },
          { icon: KeyRound, t: "Private details stay sealed", b: "Phone and bank details are encrypted, never shown to the AI." },
          { icon: Hand, t: "You type the OTP", b: "The agent pauses for OTPs, CAPTCHAs and choices only you can make." },
        ].map((x) => (
          <div key={x.t} className="flex items-start gap-3">
            <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-white/10"><x.icon className="size-5 text-saffron-300" /></span>
            <span><span className="block font-bold">{x.t}</span><span className="block text-sm text-navy-100">{x.b}</span></span>
          </div>
        ))}
      </section>
      <p className="mt-4 flex items-center gap-1.5 text-xs text-slate-500"><Sparkles className="size-3.5" />Your history is private to your account and keeps only titles and links, never documents or private details.</p>
    </div>
  );
}
