import { AnimatePresence, motion } from "motion/react";
import {
  ArrowDownUp, ArrowLeft, BadgeCheck, Ban, BrainCircuit, Check, ChevronDown, CircleAlert, CircleCheck, Compass, Copy, Database, ExternalLink,
  FileText, Globe, Hand, History, Info, Keyboard, LoaderCircle, Lock, MousePointerClick, Play, Plus, ScanText, Search, ShieldAlert,
  ShieldCheck, Square, Timer, Undo2, Zap,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { agent, api, RUN_TERMINAL, runTokens, secs, type AgentRun, type RunStep, type Service } from "../api";
import { ServiceForm } from "../components/ServiceForm";
import { Button, StatusBadge, useToast } from "../components/ui";
import { useLiveFrames } from "../components/useLiveFrames";

// ------------------------------------------------------------------ step presentation
const ic = "size-4";
function stepIcon(s: RunStep): ReactNode {
  const byAction: Record<string, ReactNode> = {
    goto: <Globe className={ic} />, type: <Keyboard className={ic} />, click: <MousePointerClick className={ic} />, select: <ChevronDown className={ic} />,
    scroll: <ArrowDownUp className={ic} />, back: <Undo2 className={ic} />, fill: <Keyboard className={ic} />, check: <CircleCheck className={ic} />,
    extract: <ScanText className={ic} />, wait_for: <Timer className={ic} />,
  };
  const byKind: Record<string, ReactNode> = {
    plan: <Compass className={ic} />, search: <Search className={ic} />, extract: <ScanText className={ic} />, done: <CircleCheck className={ic} />,
    approval: <ShieldCheck className={ic} />, human: <Hand className={ic} />, security: <ShieldAlert className={ic} />, refusal: <Ban className={ic} />,
    skill: <Zap className={ic} />, handoff: <FileText className={ic} />, info: <Info className={ic} />, error: <CircleAlert className={ic} />,
  };
  return (s.kind === "browser" && byAction[s.action?.name ?? ""]) || byKind[s.kind] || <BrainCircuit className={ic} />;
}

const tone: Record<string, string> = {
  plan: "bg-violet-400/15 text-violet-200", search: "bg-sky-400/15 text-sky-200", browser: "bg-white/10 text-slate-200",
  extract: "bg-emerald-400/15 text-emerald-200", done: "bg-emerald-400/20 text-emerald-200", approval: "bg-amber-400/20 text-amber-200",
  human: "bg-amber-400/20 text-amber-200", security: "bg-rose-400/15 text-rose-200", refusal: "bg-slate-400/15 text-slate-200",
  skill: "bg-amber-300/20 text-amber-100", handoff: "bg-navy-400/25 text-navy-100", info: "bg-white/5 text-slate-300", error: "bg-rose-400/15 text-rose-200",
};

function stepJson(s: RunStep) {
  const o: Record<string, unknown> = {
    step: s.step_no, previous_goal: s.previous_goal, eval: s.eval, memory: s.memory, next_goal: s.next_goal, action: s.action,
    outcome: s.outcome, ai_calls: s.ai_calls, duration_ms: s.duration_ms,
  };
  return Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined && v !== ""));
}

function strategyLabel(r: AgentRun) {
  if (r.strategy === "skill") return { text: "Tier-1 replay", icon: <Zap className="size-3.5" />, cls: "bg-amber-300/20 text-amber-100" };
  if (r.strategy === "handoff") return { text: "Filing agent", icon: <FileText className="size-3.5" />, cls: "bg-navy-400/25 text-navy-100" };
  if (r.status === "out_of_scope") return { text: "Refused", icon: <Ban className="size-3.5" />, cls: "bg-slate-400/15 text-slate-200" };
  return { text: "AI research", icon: <BrainCircuit className="size-3.5" />, cls: "bg-violet-400/15 text-violet-200" };
}

async function copy(text: string, toast: ReturnType<typeof useToast>) {
  try { await navigator.clipboard.writeText(text); toast("ok", "Copied"); } catch { toast("error", "Could not copy: select the text instead"); }
}

// ------------------------------------------------------------------ panels
function StepCard({ s, runId, token, selected, onSelect, latest }: {
  s: RunStep; runId: string; token: string | null; selected: boolean; onSelect: () => void; latest: boolean;
}) {
  const [open, setOpen] = useState(false);
  const json = stepJson(s);
  const hasJson = s.next_goal !== undefined || s.action !== undefined;
  const evalOk = s.eval?.toLowerCase().startsWith("success"), evalBad = s.eval?.toLowerCase().startsWith("fail");
  return (
    <motion.li layout initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.2 }}
      className={`rounded-xl ring-1 transition ${selected ? "bg-white/[0.07] ring-amber-300/60" : "bg-white/[0.03] ring-white/5 hover:ring-white/15"}`}>
      <button onClick={onSelect} className="flex w-full items-start gap-2.5 p-2.5 text-left" aria-pressed={selected}>
        <span className={`grid size-7 shrink-0 place-items-center rounded-lg ${tone[s.kind] ?? tone.info}`}>{stepIcon(s)}</span>
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline gap-2">
            <span className="font-mono text-[11px] text-slate-500">#{s.step_no}</span>
            <span className={`text-[13px] font-semibold leading-snug ${latest ? "text-white" : "text-slate-200"}`}>{s.title}</span>
          </span>
          {s.next_goal && s.next_goal !== s.title && s.kind !== "plan" && <span className="mt-0.5 block font-mono text-[11.5px] leading-snug text-slate-400">→ {s.next_goal}</span>}
          {s.kind === "plan" && s.plan && (
            <span className="mt-1 block font-mono text-[11.5px] text-violet-200/90">intent: {String(s.plan.intent)} · search: “{String(s.plan.search_query)}”</span>
          )}
          {s.eval && <span className={`mt-1 inline-block rounded px-1.5 font-mono text-[10.5px] ${evalOk ? "bg-emerald-400/10 text-emerald-300" : evalBad ? "bg-rose-400/10 text-rose-300" : "bg-white/5 text-slate-400"}`}>eval: {s.eval}</span>}
          {s.outcome && s.outcome !== "ok" && <span className={`ml-1 mt-1 inline-block rounded px-1.5 font-mono text-[10.5px] ${s.outcome.startsWith("BLOCKED") ? "bg-rose-400/10 text-rose-300" : "bg-white/5 text-slate-400"}`}>{s.outcome}</span>}
        </span>
        <span className="flex shrink-0 flex-col items-end gap-1">
          <span className="font-mono text-[10.5px] text-slate-500">{secs(s.t_ms)}</span>
          {s.screenshot && <img src={agent.shot(runId, s.step_no, token)} alt="" loading="lazy" className="h-9 w-14 rounded object-cover object-top ring-1 ring-white/10" />}
        </span>
      </button>
      {s.kind === "search" && s.results && s.results.length > 0 && (
        <ol className="space-y-1 px-3 pb-3 pl-12">
          {s.results.map((h) => (
            <li key={h.url} className="text-[12px]"><a href={h.url} target="_blank" rel="noopener noreferrer" className="font-semibold text-sky-300 hover:underline">{h.title}</a>
              <span className="block truncate font-mono text-[10.5px] text-slate-500">{h.url.replace(/^https?:\/\//, "")}</span></li>
          ))}
        </ol>
      )}
      {s.kind === "refusal" && s.reason && <p className="px-3 pb-3 pl-12 text-[12px] text-slate-400">{s.reason}</p>}
      {hasJson && (
        <div className="px-3 pb-2.5 pl-12">
          <button onClick={() => setOpen(!open)} className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-400 hover:text-white" aria-expanded={open}>
            <ChevronDown className={`size-3.5 transition-transform ${open ? "rotate-180" : ""}`} />agent state JSON
          </button>
          <AnimatePresence initial={false}>
            {open && (
              <motion.pre initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                className="mt-1.5 overflow-x-auto rounded-lg bg-night-950/80 p-2.5 font-mono text-[11px] leading-relaxed text-emerald-100/90 ring-1 ring-white/5">
                {JSON.stringify(json, null, 2)}
              </motion.pre>
            )}
          </AnimatePresence>
        </div>
      )}
    </motion.li>
  );
}

function Browser({ runId, token, live, step, caption }: { runId: string; token: string | null; live: boolean; step: RunStep | null; caption: string | null }) {
  const { frame } = useLiveFrames(runId, token ?? "", live && !!token);
  const src = live && frame ? frame : step?.screenshot ? agent.shot(runId, step.step_no, token) : null;
  const url = (step?.url ?? "").replace(/^https?:\/\//, "").replace(/^127\.0\.0\.1:\d+/, "sandbox.swayamsevak.local");
  return (
    <div className="overflow-hidden rounded-2xl bg-night-800 shadow-2xl shadow-black/40 ring-1 ring-white/10">
      <div className="flex items-center gap-3 border-b border-white/5 bg-night-700/70 px-3 py-2">
        <div className="flex gap-1.5" aria-hidden><span className="size-3 rounded-full bg-rose-400/80" /><span className="size-3 rounded-full bg-amber-300/80" /><span className="size-3 rounded-full bg-emerald-400/80" /></div>
        <div className="flex min-w-0 flex-1 items-center gap-2 rounded-lg bg-night-900/80 px-3 py-1.5 text-xs text-slate-300">
          <Lock className="size-3.5 shrink-0 text-emerald-400" aria-hidden /><span className="truncate font-mono">{url || "about:blank"}</span>
        </div>
        {live && frame ? <span className="flex items-center gap-1.5 rounded-full bg-rose-500/15 px-2 py-0.5 text-[11px] font-bold text-rose-300"><span className="size-1.5 animate-pulse rounded-full bg-rose-400" />LIVE</span>
          : step && <span className="rounded-full bg-white/5 px-2 py-0.5 font-mono text-[11px] text-slate-400">step {step.step_no}</span>}
      </div>
      <div className="relative aspect-[16/11] bg-night-900">
        {src ? <img src={src} alt={`Browser at step ${step?.step_no ?? ""}`} className="h-full w-full object-contain object-top" />
          : (
            <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center text-slate-400">
              {live ? <LoaderCircle className="size-8 animate-spin text-amber-300" /> : <Globe className="size-8 text-slate-500" />}
              <p className="text-sm">{live ? "The agent is planning. The browser opens when it needs a page." : "No page was opened for this step."}</p>
            </div>
          )}
        <AnimatePresence mode="wait">
          {caption && (
            <motion.div key={caption} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.2 }}
              className="absolute bottom-3 left-3 right-3 mx-auto max-w-lg rounded-xl bg-white/95 px-3.5 py-2.5 text-sm font-semibold text-slate-800 shadow-xl">
              {caption}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function HumanPanel({ runId, token }: { runId: string; token: string }) {
  const { send } = useLiveFrames(runId, token, true);
  const [typed, setTyped] = useState("");
  const toast = useToast();
  const sendText = () => { if (typed) { send({ t: "type", text: typed }); setTyped(""); } };
  return (
    <div className="space-y-3 rounded-2xl bg-amber-400/10 p-4 ring-1 ring-amber-400/30">
      <p className="flex items-center gap-2 text-sm font-semibold text-amber-100"><Hand className="size-4" />Your turn. What you type goes only into the page, never to the AI.</p>
      <div className="flex gap-2">
        <input value={typed} onChange={(e) => setTyped(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), sendText())}
          aria-label="Type into the page" autoComplete="off" placeholder="Type here"
          className="min-h-11 min-w-0 flex-1 rounded-xl border border-white/10 bg-night-900 px-3 text-white outline-none focus:ring-2 focus:ring-amber-300" />
        <Button variant="saffron" onClick={sendText}>Type</Button>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" className="!bg-white/10 !text-white !ring-white/10" onClick={() => send({ t: "key", key: "Enter" })}>Enter</Button>
        <Button variant="saffron" onClick={() => agent.humanDone(runId, token).catch((e) => toast("error", e.message))}>Done</Button>
      </div>
    </div>
  );
}

function Approval({ runId, token, step }: { runId: string; token: string | null; step: RunStep | null }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const decide = async (d: "approved" | "rejected") => {
    if (!token) return;
    setBusy(true);
    try { await agent.approve(runId, token, d); } catch (e) { toast("error", (e as Error).message); } finally { setBusy(false); }
  };
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl bg-white p-4 text-slate-900 shadow-2xl ring-4 ring-amber-300/60">
      <p className="flex items-center gap-2 font-display text-lg font-extrabold text-navy-900"><ShieldCheck className="size-5 text-saffron-600" />Checkpoint: your approval</p>
      <p className="mt-1 text-sm text-slate-700">{step?.title ?? "The agent wants to press a final button."} Nothing is pressed until you say yes.</p>
      {token ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button variant="primary" loading={busy} onClick={() => decide("approved")}><Check className="size-4" />Approve</Button>
          <Button variant="secondary" disabled={busy} onClick={() => decide("rejected")}>Decline</Button>
        </div>
      ) : <p className="mt-3 text-sm font-medium text-slate-600">Waiting for the person who started this run.</p>}
    </motion.div>
  );
}

function DataPanel({ run, steps, showResult }: { run: AgentRun; steps: RunStep[]; showResult: boolean }) {
  const [tab, setTab] = useState<"data" | "json" | "sources">("data");
  const toast = useToast();
  const r = showResult ? run.result : null;
  const offer = run.extra?.offer;
  const collected = steps.flatMap((s) => s.extracted ?? []);
  return (
    <section className="glass-dark flex max-h-[44rem] flex-col rounded-2xl" aria-label="Data">
      <div className="flex items-center gap-1 border-b border-white/5 p-2" role="tablist">
        {(["data", "json", "sources"] as const).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
            className={`relative rounded-lg px-3 py-1.5 text-sm font-semibold ${tab === t ? "text-white" : "text-slate-400 hover:text-white"}`}>
            {tab === t && <motion.span layoutId="data-tab" className="absolute inset-0 rounded-lg bg-white/10" />}
            <span className="relative">{{ data: "Data", json: "JSON", sources: "Sources" }[t]}</span>
          </button>
        ))}
        {r && tab === "json" && <button onClick={() => copy(JSON.stringify(r, null, 2), toast)} className="ml-auto inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs font-semibold text-slate-300 hover:bg-white/10"><Copy className="size-3.5" />Copy</button>}
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        {run.status === "out_of_scope" && (
          <div className="rounded-xl bg-white/5 p-4 text-sm text-slate-300 ring-1 ring-white/10">
            <p className="flex items-center gap-2 font-semibold text-white"><Ban className="size-4 text-slate-300" />This is outside the demo sandbox</p>
            <p className="mt-2">{run.error}</p>
            <p className="mt-2 text-slate-400">The agent refused before opening any page. That is a guardrail, enforced in code: it can only browse the sites in the registry.</p>
          </div>
        )}
        {tab === "data" && (
          <div className="space-y-3">
            {r?.answer && <div className="rounded-xl bg-emerald-400/10 p-3 text-sm leading-relaxed text-emerald-50 ring-1 ring-emerald-400/20"><span className="mb-1 block text-[11px] font-bold uppercase tracking-wider text-emerald-300">Answer · from the pages below</span>{r.answer}</div>}
            {!r && collected.length > 0 && <p className="text-xs text-slate-400">Collected so far: {collected.length} items…</p>}
            {!r && collected.length === 0 && run.status !== "out_of_scope" && !run.extra?.handoff && (
              <p className="flex items-center gap-2 text-sm text-slate-400">{RUN_TERMINAL.has(run.status) && showResult ? <><Database className="size-4" />No data for this run.</> : <><LoaderCircle className="size-4 animate-spin" />Results appear here as the agent reads pages.</>}</p>
            )}
            {r?.items.map((it) => (
              <motion.article key={it.url} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="rounded-xl bg-white/[0.04] p-3 ring-1 ring-white/10">
                <a href={it.url} target="_blank" rel="noopener noreferrer" className="flex items-start gap-1.5 font-semibold text-white hover:text-amber-200">{it.name}<ExternalLink className="mt-1 size-3.5 shrink-0 opacity-60" /></a>
                <div className="mt-1 flex flex-wrap gap-1.5 text-[11px]">
                  {it.verified && <span className="inline-flex items-center gap-1 rounded-full bg-emerald-400/10 px-2 py-0.5 font-semibold text-emerald-300"><BadgeCheck className="size-3" />found on page</span>}
                  {it.location && <span className="rounded-full bg-white/5 px-2 py-0.5 text-slate-300">{it.location}</span>}
                </div>
                {it.summary && <p className="mt-2 text-[13px] text-slate-300">{it.summary}</p>}
                {it.eligibility && <p className="mt-2 text-[13px] text-slate-300"><span className="font-semibold text-slate-100">Eligibility: </span>{it.eligibility}</p>}
                {it.benefits && <p className="mt-1 text-[13px] text-slate-300"><span className="font-semibold text-slate-100">Benefits: </span>{it.benefits}</p>}
              </motion.article>
            ))}
            {r && r.dropped_unverified > 0 && <p className="text-xs text-slate-500">{r.dropped_unverified} item(s) the AI proposed were dropped: their name or link was not on the page.</p>}
            {offer && (
              <Link to={`/agent?service=${offer.portal_id}/${offer.service_id}&prefill=${encodeURIComponent(JSON.stringify(offer.prefill))}`}
                className="block rounded-xl bg-amber-400/10 p-3 text-sm ring-1 ring-amber-400/30 hover:bg-amber-400/15">
                <span className="flex items-center gap-1.5 font-semibold text-amber-100"><Zap className="size-4" />Check exact eligibility on myScheme</span>
                <span className="mt-1 block text-amber-100/80">Answer {offer.missing.length} more question{offer.missing.length === 1 ? "" : "s"} ({offer.missing.join(", ")}) and the recorded route runs in seconds.</span>
              </Link>
            )}
          </div>
        )}
        {tab === "json" && (r ? <pre className="overflow-x-auto font-mono text-[11.5px] leading-relaxed text-emerald-100/90">{JSON.stringify(r, null, 2)}</pre>
          : <p className="text-sm text-slate-400">The structured result appears here when the run finishes.</p>)}
        {tab === "sources" && (
          <ul className="space-y-2 text-sm">
            {(r?.sources ?? [...new Set(steps.map((s) => s.url).filter(Boolean) as string[])]).map((u) => (
              <li key={u}><a href={u} target="_blank" rel="noopener noreferrer" className="break-all font-mono text-[12px] text-sky-300 hover:underline">{u}</a></li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ page
export default function AgentRunPage() {
  const { runId = "" } = useParams();
  const [params] = useSearchParams();
  const nav = useNavigate();
  const toast = useToast();
  const token = params.get("t") ?? runTokens.get(runId);
  const [run, setRun] = useState<AgentRun | null>(null);
  const [steps, setSteps] = useState<RunStep[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [picked, setPicked] = useState<number | null>(null);
  const [replay, setReplay] = useState<{ i: number; speed: number } | null>(null);
  const [speed, setSpeed] = useState(2);
  const [service, setService] = useState<Service | null>(null);
  const [pinDistricts, setPinDistricts] = useState<string[]>([]);
  const listRef = useRef<HTMLOListElement>(null);

  useEffect(() => { const t = params.get("t"); if (t) runTokens.set(runId, t); }, [runId, params]);

  useEffect(() => {
    let es: EventSource | null = null, stop = false;
    setRun(null); setSteps([]); setPicked(null); setReplay(null);
    agent.run(runId).then(({ run, steps }) => {
      if (stop) return;
      setRun(run); setSteps(steps);
      if (RUN_TERMINAL.has(run.status)) return;
      es = new EventSource(agent.eventsUrl(runId, steps.at(-1)?.step_no ?? 0));
      es.addEventListener("step", (m) => {
        const s: RunStep = JSON.parse((m as MessageEvent).data);
        setSteps((prev) => (prev.some((p) => p.step_no === s.step_no) ? prev : [...prev, s]));
      });
      es.addEventListener("run", (m) => setRun(JSON.parse((m as MessageEvent).data)));
      es.addEventListener("end", () => es?.close());
    }).catch((e) => setError(e.message));
    return () => { stop = true; es?.close(); };
  }, [runId]);

  // A handed-off filing: load its form.
  const handoff = run?.extra?.handoff;
  useEffect(() => {
    if (!handoff) return;
    api.services().then((all) => setService(all.find((s) => s.portal_id === handoff.portal_id && s.service_id === handoff.service_id) ?? null)).catch(() => {});
  }, [handoff?.portal_id, handoff?.service_id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const pin = handoff?.prefill?.pincode;
    if (!pin || handoff?.districts?.length) return;
    api.pincode(pin).then((r) => {
      if (r.ok && r.data?.districts) setPinDistricts(r.data.districts);
    }).catch(() => {});
  }, [handoff?.prefill?.pincode, handoff?.districts]);

  // Replay: reveal recorded steps with their real gaps, sped up.
  useEffect(() => {
    if (!replay) return;
    if (replay.i >= steps.length) { const t = window.setTimeout(() => setReplay(null), 1500); return () => clearTimeout(t); }
    const gap = replay.i === 0 ? 400 : (steps[replay.i].t_ms - steps[replay.i - 1].t_ms) / replay.speed;
    const t = window.setTimeout(() => setReplay((r) => (r ? { ...r, i: r.i + 1 } : r)), Math.min(4000, Math.max(250, gap)));
    return () => clearTimeout(t);
  }, [replay, steps]);

  const visible = replay ? steps.slice(0, replay.i) : steps;
  const latest = visible.at(-1) ?? null;
  const shown = (picked != null && visible.find((s) => s.step_no === picked)) || [...visible].reverse().find((s) => s.screenshot) || latest;
  const running = !!run && !RUN_TERMINAL.has(run.status);
  const live = running && !replay && picked == null;
  // Scroll only the step list (scrollIntoView would also scroll the page away from the browser view).
  useEffect(() => { const el = listRef.current; if (el && picked == null) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" }); }, [visible.length, picked]);

  const stats = useMemo(() => {
    if (!run) return null;
    if (!replay) return run.stats;
    return { ...run.stats, ai_calls: visible.reduce((n, s) => n + (s.ai_calls ?? 0), 0), wall_ms: latest?.t_ms ?? 0, steps: visible.length };
  }, [run, replay, visible, latest]);

  if (error) return <div className="mx-auto max-w-3xl px-4 py-20 text-center text-slate-300"><CircleAlert className="mx-auto size-10 text-rose-300" /><p className="mt-3">{error}</p><Link to="/agent" className="mt-4 inline-block text-amber-300 underline">Back to the agent console</Link></div>;
  if (!run || !stats) return <div className="grid min-h-[50vh] place-items-center"><LoaderCircle className="size-8 animate-spin text-amber-300" aria-label="Loading" /></div>;

  const strat = strategyLabel(run);
  const approvalStep = [...steps].reverse().find((s) => s.kind === "approval") ?? null;

  return (
    <div className="mx-auto max-w-[96rem] px-4 py-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm">
          <Link to="/agent" className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-slate-300 hover:bg-white/5 hover:text-white"><ArrowLeft className="size-4" />Console</Link>
          <Link to="/agent/history" className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-slate-300 hover:bg-white/5 hover:text-white"><History className="size-4" />History</Link>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {running && token && <Button variant="danger" className="!min-h-9 !px-3 text-sm" onClick={() => agent.cancel(runId, token).catch((e) => toast("error", e.message))}><Square className="size-3.5" />Stop</Button>}
          {!running && steps.length > 1 && (
            <div className="flex items-center gap-1 rounded-xl bg-white/5 p-1 ring-1 ring-white/10">
              {[1, 2, 5].map((x) => (
                <button key={x} onClick={() => setSpeed(x)} aria-pressed={speed === x}
                  className={`min-h-8 rounded-lg px-2.5 font-mono text-xs font-bold ${speed === x ? "bg-amber-300 text-night-950" : "text-slate-300 hover:bg-white/10"}`}>{x}×</button>
              ))}
              <button onClick={() => { setPicked(null); setReplay({ i: 0, speed }); }} className="inline-flex min-h-8 items-center gap-1 rounded-lg px-3 text-xs font-bold text-white hover:bg-white/10">
                <Play className="size-3.5" />{replay ? "Restart" : "Replay"}
              </button>
            </div>
          )}
          <Button variant="saffron" className="!min-h-9 !px-3 text-sm" onClick={() => nav("/agent")}><Plus className="size-4" />New request</Button>
        </div>
      </div>

      <header className="mt-4">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={run.status} />
          <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold ${strat.cls}`}>{strat.icon}{strat.text}</span>
          {replay && <span className="inline-flex items-center gap-1 rounded-full bg-sky-400/15 px-2.5 py-0.5 text-xs font-bold text-sky-200"><Play className="size-3" />REPLAY of a run recorded {new Date(run.created_at).toLocaleString()} · {replay.speed}×</span>}
          {!token && running && <span className="rounded-full bg-white/5 px-2.5 py-0.5 text-xs text-slate-400">view only</span>}
        </div>
        <h1 className="mt-2 text-2xl font-extrabold text-white sm:text-3xl">{run.title ?? run.query}</h1>
        {run.title && <p className="mt-1 max-w-3xl text-slate-400">“{run.query}”</p>}
      </header>

      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[
          { k: "AI calls", v: String(stats.ai_calls), icon: <BrainCircuit className="size-4 text-violet-300" /> },
          { k: "Wall time", v: secs(stats.wall_ms), icon: <Timer className="size-4 text-sky-300" /> },
          { k: "Steps", v: String(stats.steps), icon: <ScanText className="size-4 text-emerald-300" /> },
          stats.cache_hit
            ? { k: "Tier-1 replay", v: `⚡ ${secs(stats.replay_ms ?? stats.wall_ms)}`, icon: <Zap className="size-4 text-amber-300" /> }
            : { k: "Recorded route", v: "not used", icon: <Zap className="size-4 text-slate-500" /> },
        ].map((c) => (
          <div key={c.k} className="glass-dark rounded-xl px-3 py-2.5">
            <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">{c.icon}{c.k}</div>
            <div className="mt-0.5 font-mono text-xl font-bold text-white tabular-nums">{c.v}</div>
          </div>
        ))}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-[minmax(0,22rem)_minmax(0,1fr)_minmax(0,22rem)]">
        <section className="glass-dark order-2 flex max-h-[44rem] flex-col rounded-2xl xl:order-1" aria-label="Agent reasoning">
          <div className="flex items-center justify-between border-b border-white/5 px-4 py-3">
            <span className="text-sm font-semibold text-white">{running && !replay ? "Working…" : `Steps (${visible.length})`}</span>
            {picked != null && <button onClick={() => setPicked(null)} className="text-xs font-semibold text-amber-300 hover:underline">follow latest</button>}
          </div>
          <ol ref={listRef} className="flex-1 space-y-1.5 overflow-y-auto p-2.5">
            <AnimatePresence initial={false}>
              {visible.map((s) => (
                <StepCard key={s.step_no} s={s} runId={runId} token={token} latest={s === latest} selected={shown?.step_no === s.step_no && picked != null}
                  onSelect={() => setPicked(picked === s.step_no ? null : s.step_no)} />
              ))}
            </AnimatePresence>
            {running && !replay && <li className="flex items-center gap-2 px-2 py-1.5 text-xs text-slate-400"><LoaderCircle className="size-3.5 animate-spin" />thinking…</li>}
          </ol>
        </section>

        <div className="order-1 space-y-3 lg:col-span-2 xl:order-2 xl:col-span-1">
          <Browser runId={runId} token={token} live={live} step={shown} caption={running || replay ? latest?.title ?? null : null} />
          {run.status === "awaiting_approval" && !replay && <Approval runId={runId} token={token} step={approvalStep} />}
          {run.status === "awaiting_human" && !replay && token && !run.task_id && <HumanPanel runId={runId} token={token} />}
          {run.status === "awaiting_human" && !replay && token && run.task_id && (
            <div className="rounded-2xl bg-amber-400/10 p-4 ring-1 ring-amber-400/30">
              <p className="flex items-start gap-2 text-sm font-semibold text-amber-100"><Hand className="mt-0.5 size-4 shrink-0" />{latest?.kind === "human" ? latest.title : "The portal needs an answer from you."}</p>
              <Button variant="saffron" className="mt-3" onClick={() => agent.room(runId, token).then((r) => window.open(r.path, "_blank", "noopener")).catch((e) => toast("error", e.message))}>
                <Hand className="size-4" />Answer in the agent room
              </Button>
              <p className="mt-2 text-xs text-amber-200/80">It opens in a new tab. This run continues here as soon as you tap Done there.</p>
            </div>
          )}
          {run.error && !running && run.status !== "out_of_scope" && (
            <p className="flex items-start gap-2 rounded-xl bg-rose-400/10 px-3 py-2 text-sm text-rose-200 ring-1 ring-rose-400/20"><CircleAlert className="mt-0.5 size-4 shrink-0" />{run.error}</p>
          )}
        </div>

        <div className="order-3">
          <DataPanel run={run} steps={visible} showResult={!replay || replay.i >= steps.length} />
        </div>
      </div>

      {handoff && run.status === "needs_details" && (() => {
        const missingPub = service?.inputs.filter((i) => i.source === "input" && i.required && !handoff.prefill[i.key]) ?? [];
        const isOnlyPrivate = missingPub.length === 0;
        const isOnlyDistrictAndPrivate = missingPub.length === 1 && missingPub[0].key === "district";
        const isCompact = isOnlyPrivate || isOnlyDistrictAndPrivate;
        const availDistricts = handoff.districts || (pinDistricts.length > 1 ? pinDistricts : undefined);

        return (
          <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mt-6 rounded-3xl bg-white p-5 text-slate-900 shadow-2xl shadow-black/30 sm:p-7">
            <h2 className="text-xl font-extrabold text-navy-900">{service?.description ?? "Your details"}</h2>
            <p className="text-sm text-slate-600">The agent filled these from your request. You add only what it cannot know; private fields are encrypted and never shown to the AI. Nothing is submitted until you approve the final page.</p>
            <ul className="my-5 grid gap-2 sm:grid-cols-2">
              {Object.entries(handoff.prefill).filter(([k]) => !["latitude", "longitude"].includes(k)).map(([k, v]) => (
                <li key={k} className="flex items-start gap-2 rounded-xl bg-leaf-50 px-3 py-2 text-sm ring-1 ring-leaf-100">
                  <BadgeCheck className="mt-0.5 size-4 shrink-0 text-leaf-600" />
                  <span className="min-w-0"><span className="block text-xs font-semibold text-slate-500">{service?.inputs.find((i) => i.key === k)?.label ?? k}</span><span className="break-words text-slate-900">{v}</span></span>
                </li>
              ))}
            </ul>
            {service ? (
              <ServiceForm
                service={service}
                prefill={handoff.prefill}
                hide={Object.keys(handoff.prefill)}
                districts={availDistricts}
                compactCard={isCompact}
                cardTitle="I need only this from you"
                submitLabel={isCompact ? "Start filing" : "Start the filing agent"}
                onStarted={(r) => (token ? agent.link(runId, token, r.task_id) : undefined)}
              />
            ) : <p className="flex items-center gap-2 text-slate-500"><LoaderCircle className="size-4 animate-spin" />Loading the form…</p>}
          </motion.section>
        );
      })()}
      {run.status === "handed_off" && (
        <p className="mt-6 flex items-center gap-2 rounded-xl bg-white/5 px-4 py-3 text-sm text-slate-300 ring-1 ring-white/10"><FileText className="size-4" />Handed to the filing agent. Filing status: <StatusBadge status={run.task_status ?? "queued"} /></p>
      )}
    </div>
  );
}
