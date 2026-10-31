import { motion } from "motion/react";
import {
  ArrowRight, Ban, BrainCircuit, FileText, Globe, GraduationCap, Hand, History, KeyRound, LoaderCircle, Megaphone, MousePointerClick, Radio,
  Repeat, Send, ShieldCheck, Sparkles, Wheat, Zap,
} from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { agent, api, runTokens, secs, type AgentRun, type Service } from "../api";
import { ServiceForm } from "../components/ServiceForm";
import { fadeUp, stagger, StatusBadge, useToast } from "../components/ui";

// Suggestions only fill the box: every request, typed or picked, goes through the same planner.
const CHIPS = [
  { icon: GraduationCap, label: "Scholarships after Class 10", text: "Which scholarships can an SC student from Bihar get after Class 10?" },
  { icon: Wheat, label: "PM-KISAN eligibility", text: "What does PM-KISAN give farmers and who is eligible?" },
  { icon: Zap, label: "Full profile: recorded route", text: "Schemes for a 45-year-old widowed woman farmer from rural Bihar: SC category, not a minority, no disability, not a student, self-employed, not a government employee, BPL family, in economic distress" },
  { icon: Megaphone, label: "File a grievance", text: "File a grievance about a broken streetlight near PIN 800001" },
  { icon: Ban, label: "Off-limits site", text: "Book a train ticket from Patna to Delhi on irctc.co.in" },
];

const GUARDS = [
  { icon: Globe, title: "Stays on the allow-list", body: "The browser can only open the sites in the registry. Anything else is refused before a page loads." },
  { icon: MousePointerClick, title: "Types only your words", body: "The agent may type only words from your request. Private details go through the encrypted form, never the AI." },
  { icon: Ban, title: "No Submit, no Pay", body: "Final-submit buttons wait for your Approve. Payment buttons are never pressed." },
  { icon: ShieldCheck, title: "Only what the page says", body: "Each result is kept only if its name and link are on the page the agent read. Invented items are dropped." },
  { icon: Hand, title: "Hands over, never guesses", body: "OTP, CAPTCHA or a choice only you can make: the agent stops and asks you." },
  { icon: Repeat, title: "Learns once, replays fast", body: "When a recorded route fits your request, it replays in seconds with no AI in the loop." },
];

function how(r: AgentRun) {
  if (r.strategy === "skill") return <span className="inline-flex items-center gap-1 text-amber-200"><Zap className="size-3.5" />Tier-1 replay</span>;
  if (r.strategy === "handoff") return <span className="inline-flex items-center gap-1 text-navy-100"><FileText className="size-3.5" />Filing</span>;
  if (r.status === "out_of_scope") return <span className="inline-flex items-center gap-1 text-slate-400"><Ban className="size-3.5" />Refused</span>;
  return <span className="inline-flex items-center gap-1 text-violet-300"><BrainCircuit className="size-3.5" />AI research</span>;
}

function DirectService({ id, prefill }: { id: string; prefill: Record<string, string> }) {
  const [service, setService] = useState<Service | null>(null);
  useEffect(() => { api.services().then((all) => setService(all.find((s) => `${s.portal_id}/${s.service_id}` === id) ?? null)).catch(() => {}); }, [id]);
  if (!service) return null;
  return (
    <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mt-8 rounded-3xl bg-white p-5 text-slate-900 shadow-2xl shadow-black/30 sm:p-7">
      <h2 className="text-xl font-extrabold text-navy-900">{service.description}</h2>
      <p className="mb-5 text-sm text-slate-600">{service.portal_name}{service.is_sandbox ? " · sandbox replica, not a government website" : " · live government portal"}</p>
      <ServiceForm service={service} prefill={prefill} submitLabel="Start the agent" />
    </motion.section>
  );
}

export default function AgentHome() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const toast = useToast();
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [runs, setRuns] = useState<AgentRun[] | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  const direct = params.get("service");
  let prefill: Record<string, string> = {};
  try { prefill = JSON.parse(params.get("prefill") ?? "{}"); } catch { prefill = {}; }

  useEffect(() => {
    let stop = false, timer: number | undefined;
    const tick = () => agent.runs(6).then((r) => !stop && setRuns(r)).catch(() => !stop && setRuns([])).finally(() => { if (!stop) timer = window.setTimeout(tick, 5000); });
    tick();
    return () => { stop = true; clearTimeout(timer); };
  }, []);

  async function run(e?: FormEvent) {
    e?.preventDefault();
    const q = query.trim();
    if (q.length < 3) { box.current?.focus(); return; }
    setBusy(true);
    try {
      const r = await agent.start(q);
      runTokens.set(r.run_id, r.token);
      nav(r.path);
    } catch (err) {
      toast("error", (err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-10">
      <motion.div initial="hidden" animate="show" variants={stagger} className="mx-auto max-w-3xl text-center">
        <motion.p variants={fadeUp} className="mb-3 inline-flex items-center gap-2 rounded-full bg-white/5 px-3 py-1 text-xs font-semibold text-amber-200 ring-1 ring-white/10"><Radio className="size-3.5" />Part 3 · Autonomous agent</motion.p>
        <motion.h1 variants={fadeUp} className="text-4xl font-extrabold text-white sm:text-5xl">Ask the agent anything</motion.h1>
        <motion.p variants={fadeUp} className="mt-3 text-lg text-slate-300">It plans, searches official sites, works the page in a live browser and brings back data it read there. You approve anything final.</motion.p>
      </motion.div>

      <motion.form onSubmit={run} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
        className="glass-dark mx-auto mt-8 max-w-3xl rounded-3xl p-2 ring-1 ring-amber-300/20 focus-within:ring-2 focus-within:ring-amber-300/60">
        <label htmlFor="ask" className="sr-only">Your request</label>
        <textarea id="ask" ref={box} rows={2} value={query} onChange={(e) => setQuery(e.target.value)} maxLength={500}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); run(); } }}
          placeholder="Ask anything… e.g. find schemes for a widow in rural Odisha"
          className="block w-full resize-none bg-transparent px-4 py-3 text-lg text-white placeholder:text-slate-500 outline-none" />
        <div className="flex flex-wrap items-center justify-between gap-2 px-2 pb-1">
          <p className="text-xs text-slate-400">Works on myscheme.gov.in and the sandbox. Don't type Aadhaar, phone or bank numbers: runs are listed in the public history.</p>
          <button type="submit" disabled={busy}
            className="inline-flex min-h-11 items-center gap-2 rounded-2xl bg-saffron-500 px-5 font-semibold text-navy-900 shadow-[0_8px_20px_-8px_rgb(255_153_51/0.7)] transition hover:bg-saffron-400 disabled:opacity-60">
            {busy ? <LoaderCircle className="size-4 animate-spin" /> : <Send className="size-4" />}Run
          </button>
        </div>
      </motion.form>

      <motion.div initial="hidden" animate="show" variants={stagger} className="mx-auto mt-4 flex max-w-4xl flex-wrap justify-center gap-2" aria-label="Suggestions">
        {CHIPS.map((c) => (
          <motion.button key={c.label} variants={fadeUp} whileHover={{ y: -2 }} type="button"
            onClick={() => { setQuery(c.text); box.current?.focus(); }}
            className="inline-flex min-h-10 items-center gap-1.5 rounded-full bg-white/5 px-3.5 text-sm font-medium text-slate-200 ring-1 ring-white/10 hover:bg-white/10 hover:text-white">
            <c.icon className="size-4 text-amber-300" />{c.label}
          </motion.button>
        ))}
      </motion.div>

      <div className="mx-auto mt-10 grid max-w-4xl grid-cols-2 gap-3 text-center sm:grid-cols-4">
        {[["3.7–4s", "recorded route", "0 AI calls"], ["1 call", "to refuse", "an off-limits site"], ["3/3", "layout changes", "repaired"], ["0", "private values", "sent to AI"]].map(([v, a, b]) => (
          <div key={a} className="glass-dark rounded-2xl p-4"><div className="font-display text-3xl font-extrabold text-white">{v}</div><div className="mt-1 text-xs text-slate-400">{a}<br />{b}</div></div>
        ))}
      </div>
      <p className="mt-2 text-center text-xs text-slate-500">Measured in our evaluation runs and tests (Claude Opus 5.5). Each run shows its own live numbers.</p>

      {direct && <DirectService id={direct} prefill={prefill} />}

      <section className="mt-12" aria-labelledby="recent">
        <div className="mb-3 flex items-center justify-between">
          <h2 id="recent" className="flex items-center gap-2 text-xl font-bold text-white"><History className="size-5 text-amber-300" />Recent runs</h2>
          <Link to="/agent/history" className="inline-flex items-center gap-1 text-sm font-semibold text-amber-300 hover:underline">All runs<ArrowRight className="size-4" /></Link>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {runs === null && <p className="flex items-center gap-2 text-slate-400"><LoaderCircle className="size-4 animate-spin" />Loading…</p>}
          {runs?.length === 0 && <p className="text-slate-400">No runs yet. Ask something above.</p>}
          {runs?.map((r) => (
            <Link key={r.run_id} to={`/agent/runs/${r.run_id}`} aria-label={`${r.title ?? r.query}: ${r.status.replace(/_/g, " ")}`} className="glass-dark block rounded-2xl p-4 transition hover:ring-1 hover:ring-white/20">
              <div className="flex items-center justify-between gap-2"><StatusBadge status={r.status} /><span className="text-xs">{how(r)}</span></div>
              <p className="mt-2 line-clamp-2 font-semibold text-white">{r.title ?? r.query}</p>
              <p className="mt-1 font-mono text-xs text-slate-400">{r.stats.steps} steps · {secs(r.stats.wall_ms)} · {r.stats.ai_calls} AI calls</p>
            </Link>
          ))}
        </div>
      </section>

      <section className="mt-12" aria-labelledby="guards">
        <h2 id="guards" className="mb-4 flex items-center gap-2 text-xl font-bold text-white"><ShieldCheck className="size-5 text-emerald-300" />Guardrails, enforced in code</h2>
        <motion.div initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.2 }} variants={stagger} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {GUARDS.map((g) => (
            <motion.div key={g.title} variants={fadeUp} className="glass-dark rounded-2xl p-5">
              <g.icon className="size-6 text-amber-300" aria-hidden />
              <h3 className="mt-3 font-semibold text-white">{g.title}</h3>
              <p className="mt-1 text-sm text-slate-400">{g.body}</p>
            </motion.div>
          ))}
        </motion.div>
        <p className="mt-4 flex items-center gap-2 text-xs text-slate-500"><KeyRound className="size-3.5" />Also: <Sparkles className="size-3.5" />the AI never sees your private fields; the vault encrypts them.</p>
      </section>
    </div>
  );
}
