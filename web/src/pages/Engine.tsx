import { motion } from "motion/react";
import { ArrowLeft, BookOpen, Brain, Database, FileSearch, FileText, Languages, ScanText, Search, Volume2, type LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, secs, type AppConfig } from "../api";
import { Badge, Card, NotConnected } from "../components/ui";

/** Part 1 contract: GET /api/pipeline/latest -> {question?, nodes: [{id, status: idle|running|done|error, ms?}]}. */
type NodeState = { id: string; status: "idle" | "running" | "done" | "error"; ms?: number; note?: string };

const NODES: { id: string; label: string; icon: LucideIcon; body: string; x: number; y: number }[] = [
  { id: "ingest", label: "Ingest notice", icon: FileText, body: "A .gov.in link, a PDF or pasted text", x: 8, y: 22 },
  { id: "parse", label: "Parse", icon: ScanText, body: "Text page by page; scans are read by the AI from page images", x: 31, y: 22 },
  { id: "chunk", label: "Chunk", icon: BookOpen, body: "Pieces that keep their page number", x: 54, y: 22 },
  { id: "embed", label: "Embed", icon: Database, body: "Not used: documents fit the model, long ones use keyword ranking", x: 77, y: 22 },
  { id: "retrieve", label: "Retrieve", icon: Search, body: "The parts that matter for the question", x: 77, y: 70 },
  { id: "reason", label: "Explain with quotes", icon: Brain, body: "Rights, eligibility, impact; each quote checked against the document", x: 54, y: 70 },
  { id: "translate", label: "Translate", icon: Languages, body: "Into the citizen's language", x: 31, y: 70 },
  { id: "voice", label: "Voice", icon: Volume2, body: "A short spoken explainer", x: 8, y: 70 },
];

export default function Engine() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [state, setState] = useState<{ question?: string; nodes: NodeState[] } | null>(null);
  useEffect(() => { api.config().then(setConfig).catch(() => {}); }, []);
  useEffect(() => {
    if (!config?.part1_connected) return;
    let stop = false, timer: number | undefined;
    const tick = () => api.part1("api/pipeline/latest").then((s) => !stop && setState(s)).catch(() => {}).finally(() => { if (!stop) timer = window.setTimeout(tick, 1200); });
    tick();
    return () => { stop = true; clearTimeout(timer); };
  }, [config?.part1_connected]);
  const st = (id: string) => state?.nodes.find((n) => n.id === id);

  return (
    <div className="mx-auto max-w-7xl px-4 py-10">
      <Link to="/schemes" className="inline-flex items-center gap-1 text-sm font-semibold text-navy-700 hover:text-saffron-700"><ArrowLeft className="size-4" />Back to schemes</Link>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
        <div>
          <Badge tone="leaf">Part 1 · Engine room</Badge>
          <h1 className="mt-3 text-4xl font-extrabold text-navy-900">How an answer is made</h1>
          <p className="mt-2 max-w-2xl text-lg text-slate-700">Each stage lights up as the explainer works, with how long it took. Answers always come with the official source they were read from.</p>
        </div>
        {state?.question && <Card variant="glass" className="max-w-sm px-4 py-3 text-sm"><span className="font-semibold text-navy-900">Now answering:</span> {state.question}</Card>}
      </div>

      <div className="relative mt-8 overflow-hidden rounded-3xl bg-navy-900 p-4 sm:p-8">
        <div className="relative mx-auto aspect-[16/9] min-h-[26rem] w-full max-w-5xl">
          <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
            {NODES.slice(0, -1).map((n, i) => {
              const m = NODES[i + 1];
              const live = st(m.id)?.status === "running" || st(m.id)?.status === "done";
              return (
                <motion.line key={n.id} x1={n.x + 7} y1={n.y + 6} x2={m.x + 7} y2={m.y + 6} stroke={live ? "#FF9933" : "#2B3F73"} strokeWidth="0.5"
                  strokeDasharray="1.5 1.2" vectorEffect="non-scaling-stroke" style={{ strokeWidth: 3 }}
                  animate={live ? { strokeDashoffset: [0, -5.4] } : {}} transition={{ duration: 0.8, repeat: Infinity, ease: "linear" }} />
              );
            })}
          </svg>
          {NODES.map((n, i) => {
            const s = st(n.id);
            const cls = s?.status === "done" ? "bg-leaf-500/20 ring-leaf-400 text-white" : s?.status === "running" ? "bg-saffron-500/25 ring-saffron-400 text-white pulse-ring" : s?.status === "error" ? "bg-red-500/20 ring-red-400 text-white" : "bg-white/5 ring-white/10 text-slate-300";
            return (
              <motion.div key={n.id} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.05 }}
                className={`absolute w-[20%] min-w-[7.5rem] rounded-2xl p-3 ring-1 backdrop-blur ${cls}`} style={{ left: `${n.x - 3}%`, top: `${n.y - 8}%` }}>
                <div className="flex items-center gap-2">
                  <span className="grid size-8 shrink-0 place-items-center rounded-xl bg-white/10"><n.icon className="size-4" /></span>
                  <span className="text-sm font-bold leading-tight">{n.label}</span>
                </div>
                <p className="mt-1.5 hidden text-xs text-slate-300 sm:block">{n.body}</p>
                <div className="mt-1.5 font-mono text-[11px] text-slate-400">{s?.ms != null ? secs(s.ms) : s?.status === "running" ? "working…" : "idle"}</div>
                {s?.note && <div className="mt-0.5 hidden font-mono text-[10.5px] text-amber-200/80 sm:block">{s.note}</div>}
              </motion.div>
            );
          })}
          <div className="absolute inset-x-0 bottom-0 flex items-center justify-center gap-2 text-xs text-slate-400"><FileSearch className="size-4" />Every answer cites the clause it came from</div>
        </div>
      </div>

      {config && !config.part1_connected && (
        <div className="mt-6"><NotConnected part="The explainer engine (Part 1)" endpoint="PART1_API_URL" what="When Part 1 is running, its pipeline events drive this canvas: each stage lights up with its real timing." /></div>
      )}
    </div>
  );
}
