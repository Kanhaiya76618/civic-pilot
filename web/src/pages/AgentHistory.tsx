import { motion } from "motion/react";
import { ArrowLeft, Ban, BrainCircuit, FileText, History, LoaderCircle, Zap } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { agent, secs, type AgentRun } from "../api";
import { StatusBadge } from "../components/ui";

function How({ r }: { r: AgentRun }) {
  if (r.strategy === "skill") return <span className="inline-flex items-center gap-1 rounded-full bg-amber-300/15 px-2 py-0.5 text-xs font-bold text-amber-200"><Zap className="size-3.5" />Tier-1 replay</span>;
  if (r.strategy === "handoff") return <span className="inline-flex items-center gap-1 text-xs text-navy-100"><FileText className="size-3.5" />Filing</span>;
  if (r.status === "out_of_scope") return <span className="inline-flex items-center gap-1 text-xs text-slate-400"><Ban className="size-3.5" />Refused</span>;
  return <span className="inline-flex items-center gap-1 text-xs text-violet-300"><BrainCircuit className="size-3.5" />AI research</span>;
}

export default function AgentHistory() {
  const [runs, setRuns] = useState<AgentRun[] | null>(null);
  const nav = useNavigate();
  useEffect(() => {
    let stop = false, timer: number | undefined;
    const tick = () => agent.runs(100).then((r) => !stop && setRuns(r)).catch(() => !stop && setRuns([])).finally(() => { if (!stop) timer = window.setTimeout(tick, 5000); });
    tick();
    return () => { stop = true; clearTimeout(timer); };
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <Link to="/agent" className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-sm text-slate-300 hover:bg-white/5 hover:text-white"><ArrowLeft className="size-4" />Agent console</Link>
      <h1 className="mt-3 flex items-center gap-2 text-3xl font-extrabold text-white"><History className="size-7 text-amber-300" />Task history</h1>
      <p className="mt-1 text-slate-400">Every run, with its steps, screenshots and data. Open one to replay it. Refreshes every 5 seconds.</p>

      <div className="glass-dark mt-6 overflow-x-auto rounded-2xl">
        <table className="w-full min-w-[46rem] text-sm">
          <thead className="text-left text-xs uppercase tracking-wider text-slate-400">
            <tr>{["Request", "How", "Status", "Steps", "Time", "AI calls", "Results", "When"].map((h) => <th key={h} className="px-4 py-3 font-semibold">{h}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {runs === null && <tr><td colSpan={8} className="px-4 py-6 text-slate-400"><LoaderCircle className="inline size-4 animate-spin" /> Loading…</td></tr>}
            {runs?.length === 0 && <tr><td colSpan={8} className="px-4 py-6 text-slate-400">No runs yet. <Link to="/agent" className="text-amber-300 underline">Ask the agent something.</Link></td></tr>}
            {runs?.map((r) => (
              <motion.tr key={r.run_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} onClick={() => nav(`/agent/runs/${r.run_id}`)}
                className="cursor-pointer text-slate-200 hover:bg-white/[0.04]">
                <td className="max-w-[22rem] px-4 py-3">
                  <Link to={`/agent/runs/${r.run_id}`} className="font-semibold text-white hover:text-amber-200" onClick={(e) => e.stopPropagation()}>{r.title ?? r.query}</Link>
                  <span className="block truncate text-xs text-slate-500">{r.query}</span>
                </td>
                <td className="px-4 py-3"><How r={r} /></td>
                <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                <td className="px-4 py-3 font-mono">{r.stats.steps}</td>
                <td className="px-4 py-3 font-mono">{secs(r.stats.wall_ms)}</td>
                <td className="px-4 py-3 font-mono">{r.stats.ai_calls}</td>
                <td className="px-4 py-3 font-mono text-xs">{r.result ? `${r.result.items.length} items` : "–"}</td>
                <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-400">{new Date(r.created_at).toLocaleString()}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
