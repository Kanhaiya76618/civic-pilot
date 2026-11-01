import { AnimatePresence, motion } from "motion/react";
import { History, LoaderCircle, Search, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { me, type HistoryEntry, type HistoryKind } from "../api";
import { HistoryRow, KINDS } from "../components/HomeWidgets";
import { Button, useToast } from "../components/ui";

const TABS: (HistoryKind | "all")[] = ["all", "explain", "agent", "lookup", "filing", "report", "news"];

function dayLabel(iso: string) {
  const d = new Date(iso), today = new Date();
  const diff = Math.round((new Date(today.toDateString()).getTime() - new Date(d.toDateString()).getTime()) / 864e5);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  if (diff < 7) return d.toLocaleDateString("en-IN", { weekday: "long" });
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
}

export default function MyHistory() {
  const toast = useToast();
  const [all, setAll] = useState<HistoryEntry[] | null>(null);
  const [tab, setTab] = useState<HistoryKind | "all">("all");
  const [q, setQ] = useState("");
  const [confirming, setConfirming] = useState(false);
  useEffect(() => { me.history().then(setAll).catch((e) => { toast("error", e.message); setAll([]); }); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: all?.length ?? 0 };
    all?.forEach((h) => { c[h.kind] = (c[h.kind] ?? 0) + 1; });
    return c;
  }, [all]);
  const groups = useMemo(() => {
    const list = (all ?? []).filter((h) => (tab === "all" || h.kind === tab)
      && (!q.trim() || `${h.title} ${h.subtitle ?? ""}`.toLowerCase().includes(q.trim().toLowerCase())));
    const out: [string, HistoryEntry[]][] = [];
    list.forEach((h) => { const k = dayLabel(h.created_at); const g = out.find(([l]) => l === k); g ? g[1].push(h) : out.push([k, [h]]); });
    return out;
  }, [all, tab, q]);

  async function remove(h: HistoryEntry) {
    try { await me.remove(h.id); setAll((a) => a?.filter((x) => x.id !== h.id) ?? null); }
    catch (e) { toast("error", (e as Error).message); }
  }
  async function clear() {
    try {
      const r = await me.clear(tab === "all" ? undefined : tab);
      setAll((a) => a?.filter((h) => tab !== "all" && h.kind !== tab) ?? null);
      toast("ok", `Removed ${r.deleted} entr${r.deleted === 1 ? "y" : "ies"}`);
    } catch (e) { toast("error", (e as Error).message); }
    setConfirming(false);
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-3xl font-extrabold text-navy-900"><History className="size-7 text-saffron-600" />My history</h1>
          <p className="mt-1 text-slate-600">Everything you explained, asked, filed, reported or saved. Private to your account.</p>
        </div>
        <label className="flex min-h-11 items-center gap-2 rounded-xl bg-white px-3 ring-1 ring-navy-100 focus-within:ring-2 focus-within:ring-navy-300">
          <Search className="size-4 text-slate-400" aria-hidden /><span className="sr-only">Search history</span>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" className="w-44 bg-transparent outline-none" />
        </label>
      </div>

      <div className="mt-6 flex flex-wrap gap-1.5" role="tablist" aria-label="History type">
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => { setTab(t); setConfirming(false); }}
            className={`relative inline-flex min-h-10 items-center gap-2 rounded-full px-4 text-sm font-semibold transition ${tab === t ? "text-white" : "bg-white text-navy-700 ring-1 ring-navy-100 hover:bg-navy-50"}`}>
            {tab === t && <motion.span layoutId="hist-tab" className="absolute inset-0 rounded-full bg-navy-700" transition={{ type: "spring", stiffness: 400, damping: 32 }} />}
            <span className="relative">{t === "all" ? "All" : KINDS[t].label}</span>
            <span className={`relative rounded-full px-1.5 text-xs ${tab === t ? "bg-white/20" : "bg-navy-50"}`}>{counts[t] ?? 0}</span>
          </button>
        ))}
      </div>

      <div className="mt-6 rounded-3xl bg-white p-3 shadow-[0_18px_44px_-30px_rgb(19_48_107/.45)] ring-1 ring-navy-100 sm:p-5">
        {all === null && <p className="flex items-center gap-2 p-4 text-slate-500"><LoaderCircle className="size-4 animate-spin" />Loading your history…</p>}
        {all !== null && groups.length === 0 && (
          <div className="p-6 text-center text-slate-600">
            <p className="font-semibold text-navy-900">{q ? "Nothing matches your search." : "Nothing here yet."}</p>
            <p className="mt-1 text-sm">Explain a notice on <Link to="/schemes" className="font-semibold text-navy-700 underline">Know your schemes</Link>, ask the <Link to="/agent" className="font-semibold text-navy-700 underline">agent</Link>, or save news from your home page.</p>
          </div>
        )}
        <AnimatePresence initial={false}>
          {groups.map(([day, items]) => (
            <motion.section key={day} layout className="mb-4 last:mb-0">
              <h2 className="px-2 pb-1 text-xs font-bold uppercase tracking-wider text-slate-500">{day}</h2>
              <ul className="space-y-0.5">{items.map((h) => <HistoryRow key={h.id} h={h} onDelete={remove} />)}</ul>
            </motion.section>
          ))}
        </AnimatePresence>
      </div>

      {(all?.length ?? 0) > 0 && (
        <div className="mt-4 flex justify-end">
          {confirming ? (
            <div className="flex items-center gap-2 rounded-2xl bg-red-50 p-2 ring-1 ring-red-200">
              <span className="px-2 text-sm font-semibold text-red-800">Remove {tab === "all" ? "all history" : `all ${KINDS[tab].label.toLowerCase()} entries`}?</span>
              <Button variant="danger" onClick={clear}>Remove</Button>
              <Button variant="ghost" onClick={() => setConfirming(false)}>Cancel</Button>
            </div>
          ) : (
            <Button variant="ghost" onClick={() => setConfirming(true)} className="!text-red-700 hover:!bg-red-50"><Trash2 className="size-4" />Clear {tab === "all" ? "history" : KINDS[tab].label.toLowerCase()}</Button>
          )}
        </div>
      )}
    </div>
  );
}
