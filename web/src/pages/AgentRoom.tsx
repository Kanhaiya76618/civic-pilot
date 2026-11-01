import { AnimatePresence, motion } from "motion/react";
import {
  ArrowLeft, BadgeCheck, Bot, BrainCircuit, ChevronDown, CircleAlert, CircleCheck, Clock, Copy, ExternalLink, FileText, Globe,
  Hand, Keyboard, LoaderCircle, Lock, MousePointerClick, PenLine, Receipt as ReceiptIcon, ScrollText, Search, ShieldAlert, ShieldCheck,
  Smartphone, Sparkles, Timer, Upload, Workflow, Wrench, X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, secs, TERMINAL, type Receipt, type TaskEvent, type TaskState } from "../api";
import { Button, StatusBadge, useToast } from "../components/ui";
import { useLiveFrames } from "../components/useLiveFrames";

// ------------------------------------------------------------------ data helpers
type Line = { key: string; icon: ReactNode; text: string; sub?: string; tone: "info" | "ok" | "warn" | "bad" | "ai"; at: number };

function tOffset(e: TaskEvent, t0: number) { return new Date(e.at).getTime() - t0; }

function lineFor(e: TaskEvent, t0: number, portalName: string): Line | null {
  const at = tOffset(e, t0), d = e.data, key = String(e.seq);
  const ic = "size-4";
  if (e.kind === "step") {
    const label = d.label ? `“${d.label}”` : "";
    const map: Record<string, [ReactNode, string]> = {
      goto: [<Globe className={ic} />, `Opening ${!d.host || /^(127\.|localhost)/.test(d.host) ? portalName : d.host}`],
      fill: [<PenLine className={ic} />, `Typing ${label}`],
      select: [<ChevronDown className={ic} />, `Choosing ${label}`],
      check: [<CircleCheck className={ic} />, `Ticking ${label}`],
      click: [<MousePointerClick className={ic} />, `Clicking ${label}`],
      upload: [<Upload className={ic} />, `Uploading ${label}`],
      press: [<Keyboard className={ic} />, "Pressing a key"],
      wait_for: [<Clock className={ic} />, "Waiting for the next page"],
      extract: [<Search className={ic} />, "Reading the results off the page"],
      human_step: [<Hand className={ic} />, `Handing over to you: ${d.kind?.toUpperCase() ?? "help needed"}`],
      approval_gate: [<FileText className={ic} />, "Preparing your approval card"],
    };
    const [icon, text] = map[d.do ?? ""] ?? [<Workflow className={ic} />, e.message];
    return { key, icon, text, sub: d.value, tone: d.do === "human_step" ? "warn" : "info", at };
  }
  if (e.kind === "status") {
    if (e.status === "queued") return null;
    const text = e.message.startsWith("Running ") ? `Starting the browser on ${portalName}` : e.message;
    return { key, icon: <Workflow className={ic} />, text, tone: e.status === "completed" ? "ok" : "info", at };
  }
  const kinds: Record<string, [ReactNode, Line["tone"]]> = {
    info: [<CircleCheck className={ic} />, "info"], human_needed: [<Hand className={ic} />, "warn"], approval_needed: [<FileText className={ic} />, "warn"],
    heal: [<Wrench className={ic} />, "ai"], reasoning: [<BrainCircuit className={ic} />, "ai"], security: [<ShieldAlert className={ic} />, "bad"],
    receipt: [<ReceiptIcon className={ic} />, "ok"], error: [<CircleAlert className={ic} />, "bad"],
  };
  const k = kinds[e.kind];
  if (!k) return null;
  return { key, icon: k[0], text: e.kind === "reasoning" ? `AI: ${e.message}` : e.message, tone: k[1], at };
}

const toneCls: Record<Line["tone"], string> = {
  info: "text-slate-300 bg-white/5", ok: "text-emerald-300 bg-emerald-400/10", warn: "text-amber-300 bg-amber-400/10",
  bad: "text-rose-300 bg-rose-400/10", ai: "text-violet-300 bg-violet-400/10",
};

// ------------------------------------------------------------------ pipeline strip
function Pipeline({ s }: { s: TaskState }) {
  const ev = s.events, t0 = ev.length ? new Date(ev[0].at).getTime() : 0;
  const statuses = new Set(ev.map((e) => e.status));
  const has = (k: string) => ev.some((e) => e.kind === k);
  const firstAt = (pred: (e: TaskEvent) => boolean) => { const e = ev.find(pred); return e ? tOffset(e, t0) : null; };
  const stopped = s.status === "failed" || s.status === "needs_review";
  const nodes = [
    { label: "Checks", icon: ShieldCheck, on: statuses.has("validating"), done: statuses.has("preparing_docs") || statuses.has("running"), at: firstAt((e) => e.status === "preparing_docs") },
    { label: "Documents", icon: FileText, on: statuses.has("preparing_docs"), done: statuses.has("running"), at: firstAt((e) => e.status === "running") },
    { label: "Browser", icon: Globe, on: statuses.has("running"), done: s.status === "completed" || has("approval_needed"), at: firstAt((e) => e.kind === "step") },
    { label: s.strategy === "explore" ? "AI explore" : "AI repair", icon: BrainCircuit, on: has("reasoning") || has("heal"), done: has("reasoning") || has("heal"), skip: !has("reasoning") && !has("heal"), at: firstAt((e) => e.kind === "reasoning" || e.kind === "heal") },
    { label: "You", icon: Hand, on: has("human_needed"), done: has("human_needed") && s.status !== "awaiting_human", skip: !has("human_needed"), at: firstAt((e) => e.kind === "human_needed") },
    { label: "Approval", icon: FileText, on: has("approval_needed"), done: statuses.has("submitting") || s.mode === "dry_run" && has("approval_needed"), skip: !has("approval_needed"), at: firstAt((e) => e.kind === "approval_needed") },
    { label: "Receipt", icon: ReceiptIcon, on: has("receipt"), done: has("receipt"), at: firstAt((e) => e.kind === "receipt") },
  ];
  return (
    <ol className="flex items-center gap-1 overflow-x-auto pb-1" aria-label="Task pipeline">
      {nodes.map((n, i) => {
        const Icon = n.icon;
        const state = n.done ? "done" : n.on ? (stopped ? "bad" : "on") : n.skip && TERMINAL.has(s.status) ? "skip" : "idle";
        const cls = {
          done: "border-b-2 border-leaf-500 bg-emerald-400/15 text-emerald-200 ring-emerald-400/30", on: "border-b-2 border-saffron-500 bg-saffron-400/15 text-saffron-100 ring-saffron-400/40 pulse-ring",
          bad: "bg-rose-400/15 text-rose-200 ring-rose-400/40", skip: "bg-white/[0.03] text-slate-500 ring-white/5 border-dashed", idle: "bg-white/5 text-slate-400 ring-white/10",
        }[state];
        return (
          <li key={n.label} className="flex shrink-0 items-center gap-1">
            <motion.div layout className={`flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-semibold ring-1 ${cls}`}>
              <Icon className="size-4" aria-hidden />
              <span>{n.label}</span>
              {n.at != null && state === "done" && <span className="font-mono text-[10px] opacity-70">+{secs(n.at)}</span>}
              {state === "skip" && <span className="text-[10px] font-normal">not needed</span>}
            </motion.div>
            {i < nodes.length - 1 && <span className={`h-px w-4 ${n.done ? "bg-emerald-400/50" : "bg-white/10"}`} aria-hidden />}
          </li>
        );
      })}
    </ol>
  );
}

// ------------------------------------------------------------------ live browser
function BrowserCard({ s, taskId, token, caption }: { s: TaskState; taskId: string; token: string; caption: Line | null }) {
  const running = !TERMINAL.has(s.status);
  const { frame, send } = useLiveFrames(taskId, token, running);
  const [typed, setTyped] = useState("");
  const [sms, setSms] = useState<string | null>(null);
  const toast = useToast();
  const imgRef = useRef<HTMLImageElement>(null);
  const url = s.page_url ?? s.receipt?.result?.source_url ?? "";
  const shownUrl = url.replace(/^https?:\/\//, "").replace(/^127\.0\.0\.1:\d+/, "sandbox.swayamsevak.local");
  const finalSrc = s.has_final ? `/citizen/${taskId}/final.png?t=${encodeURIComponent(token)}` : null;
  const src = running ? frame : finalSrc ?? frame;
  const human = s.human;

  const click = (e: React.MouseEvent<HTMLImageElement>) => {
    if (!human) return;
    const r = e.currentTarget.getBoundingClientRect();
    send({ t: "click", x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height });
  };
  const sendText = () => { if (typed) { send({ t: "type", text: typed }); setTyped(""); } };

  return (
    <div className="overflow-hidden rounded-2xl bg-night-800 ring-1 ring-white/10 shadow-2xl shadow-black/40">
      <div className="flex items-center gap-3 border-b border-white/5 bg-night-700/70 px-3 py-2">
        <div className="flex gap-1.5" aria-hidden><span className="size-3 rounded-full bg-rose-400/80" /><span className="size-3 rounded-full bg-amber-300/80" /><span className="size-3 rounded-full bg-emerald-400/80" /></div>
        <div className="flex min-w-0 flex-1 items-center gap-2 rounded-lg bg-night-900/80 px-3 py-1.5 text-xs text-slate-300">
          <Lock className="size-3.5 shrink-0 text-emerald-400" aria-hidden />
          <span className="truncate font-mono">{shownUrl || (running ? "starting browser…" : "final page")}</span>
        </div>
        {running && frame && <span className="flex items-center gap-1.5 rounded-full bg-rose-500/15 px-2 py-0.5 text-[11px] font-bold text-rose-300"><span className="size-1.5 animate-pulse rounded-full bg-rose-400" />LIVE</span>}
        {!running && finalSrc && shownUrl && <span className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] font-semibold text-slate-400">final page</span>}
      </div>
      <div className={`relative bg-night-900 ${running || !src ? "aspect-[16/11] max-h-[70vh]" : "max-h-[70vh] overflow-y-auto"}`}>
        {src ? (
          <img ref={imgRef} src={src} alt={running ? "Live view of the portal the agent is operating" : "Final page of the portal"} onClick={click}
            className={running ? `h-full w-full object-contain object-top ${human ? "cursor-crosshair" : ""}` : "h-auto w-full"} />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-slate-400">
            <LoaderCircle className="size-8 animate-spin text-amber-300" />
            <p className="text-sm">{running ? "Connecting to the agent's browser…" : "No screenshot for this run"}</p>
          </div>
        )}
        <AnimatePresence mode="wait">
          {caption && running && !human && (
            <motion.div key={caption.key} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.2 }}
              className="absolute bottom-4 left-4 right-4 mx-auto flex max-w-lg items-center gap-3 rounded-2xl bg-white/95 px-4 py-3 text-sm text-slate-800 shadow-xl">
              <span className="grid size-8 shrink-0 place-items-center rounded-full bg-navy-700 text-white"><Bot className="size-4" /></span>
              <span className="min-w-0"><span className="font-semibold">{caption.text}</span>{caption.sub && <span className="block truncate text-slate-500">{caption.sub}</span>}</span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <AnimatePresence>
        {human && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden border-t border-amber-400/30 bg-amber-400/10">
            <div className="space-y-3 p-4">
              <p className="flex items-start gap-2 text-sm font-semibold text-amber-100"><Hand className="mt-0.5 size-4 shrink-0" />{human.instructions}</p>
              <p className="text-xs text-amber-200/80">Tap the field in the picture above, then type here. What you type goes only into the portal: never stored, never shown to the AI.</p>
              <div className="flex gap-2">
                <input value={typed} onChange={(e) => setTyped(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), sendText())}
                  aria-label="Type into the portal" autoComplete="off" className="min-h-11 flex-1 rounded-xl border border-white/10 bg-night-900 px-3 text-white outline-none focus:ring-2 focus:ring-amber-300" placeholder="Type here" />
                <Button variant="saffron" onClick={sendText}>Type</Button>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" className="!bg-white/10 !text-white !ring-white/10" onClick={() => send({ t: "key", key: "Backspace" })}>⌫ Backspace</Button>
                <Button variant="secondary" className="!bg-white/10 !text-white !ring-white/10" onClick={() => send({ t: "key", key: "Enter" })}>Enter</Button>
                <Button variant="saffron" onClick={() => api.humanDone(taskId, token).catch((e) => toast("error", e.message))}>Done</Button>
                <Button variant="ghost" className="!text-rose-300 hover:!bg-rose-400/10" onClick={() => api.humanCancel(taskId, token).catch((e) => toast("error", e.message))}>Cancel</Button>
                {s.portal.is_sandbox && human.kind === "otp" && (
                  <Button variant="ghost" className="!text-amber-200 hover:!bg-white/5" onClick={async () => {
                    const r = await api.sandboxSms();
                    const text = r.messages.at(-1)?.text ?? "No SMS yet";
                    setSms(text);
                    const m = text.match(/\b\d{6}\b/);
                    if (m) setTyped(m[0]);
                  }}>
                    <Smartphone className="size-4" /> Open sandbox phone
                  </Button>
                )}
              </div>
              {sms && <p className="flex items-center gap-2 rounded-xl bg-night-900 px-3 py-2 font-mono text-sm text-amber-100"><Smartphone className="size-4 shrink-0" />{sms}</p>}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ------------------------------------------------------------------ side panels
function Activity({ lines, s }: { lines: Line[]; s: TaskState }) {
  const [open, setOpen] = useState(true);
  const running = !TERMINAL.has(s.status);
  const endRef = useRef<HTMLDivElement>(null);
  // Braces matter: scrollIntoView returns a Promise in current Chrome, and an effect may only return a cleanup function.
  useEffect(() => { endRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [lines.length]);
  return (
    <section className="glass-dark flex max-h-[34rem] flex-col rounded-2xl" aria-label="Activity">
      <button onClick={() => setOpen(!open)} className="flex items-center justify-between gap-2 border-b border-white/5 px-4 py-3 text-left" aria-expanded={open}>
        <span className="text-sm font-semibold text-white">{running ? "Working…" : `Worked for ${secs(s.timing.total_ms)}`}</span>
        <ChevronDown className={`size-4 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <ol className="flex-1 space-y-1 overflow-y-auto p-3 font-mono text-[12.5px]">
          <AnimatePresence initial={false}>
            {lines.map((l, i) => (
              <motion.li key={l.key} layout initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.18 }} className="flex gap-2 rounded-lg px-2 py-1.5 hover:bg-white/[0.03]">
                <span className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-md ${toneCls[l.tone]}`}>{l.icon}</span>
                <span className="min-w-0 flex-1">
                  <span className={`block break-words font-sans text-[13px] ${i === lines.length - 1 && running ? "text-white" : "text-slate-300"}`}>{l.text}</span>
                  {l.sub && <span className="block truncate text-slate-500">{l.sub}</span>}
                </span>
                <span className="shrink-0 text-[10.5px] text-slate-500">{secs(l.at)}</span>
              </motion.li>
            ))}
          </AnimatePresence>
          <div ref={endRef} />
        </ol>
      )}
    </section>
  );
}

function Reasoning({ s }: { s: TaskState }) {
  const items = s.events.filter((e) => ["reasoning", "heal", "security", "human_needed", "approval_needed", "receipt", "error"].includes(e.kind) && !(e.kind === "human_needed" && e.message.startsWith("Not done yet")));
  const meta: Record<string, { label: string; cls: string; icon: ReactNode }> = {
    reasoning: { label: "AI decision", cls: "bg-violet-400/15 text-violet-200", icon: <BrainCircuit className="size-3.5" /> },
    heal: { label: "Repair", cls: "bg-sky-400/15 text-sky-200", icon: <Wrench className="size-3.5" /> },
    security: { label: "Blocked / flagged", cls: "bg-rose-400/15 text-rose-200", icon: <ShieldAlert className="size-3.5" /> },
    human_needed: { label: "Your turn", cls: "bg-amber-400/15 text-amber-200", icon: <Hand className="size-3.5" /> },
    approval_needed: { label: "Approval", cls: "bg-amber-400/15 text-amber-200", icon: <FileText className="size-3.5" /> },
    receipt: { label: "Complete", cls: "bg-emerald-400/15 text-emerald-200", icon: <CircleCheck className="size-3.5" /> },
    error: { label: "Stopped safely", cls: "bg-rose-400/15 text-rose-200", icon: <CircleAlert className="size-3.5" /> },
  };
  return (
    <section className="glass-dark flex max-h-[34rem] flex-col rounded-2xl" aria-label="Reasoning">
      <div className="flex items-center justify-between border-b border-white/5 px-4 py-3">
        <span className="flex items-center gap-2 text-sm font-semibold text-white"><Sparkles className="size-4 text-violet-300" />Reasoning & safety</span>
        <span className="font-mono text-xs text-slate-400">{items.length} events</span>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto p-3">
        {items.length === 0 && (
          <p className="rounded-xl bg-white/[0.03] p-4 text-sm text-slate-400">
            {s.strategy === "explore" ? "The AI's decisions will appear here, one card per turn." : "Replaying a learned route: no AI decisions needed so far. Repairs, safety blocks and your hand-offs appear here."}
          </p>
        )}
        <AnimatePresence initial={false}>
          {items.map((e, i) => {
            const m = meta[e.kind];
            return (
              <motion.article key={e.seq} layout initial={{ opacity: 0, y: 10, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.22 }}
                className="rounded-xl bg-night-800/90 p-3 ring-1 ring-white/5">
                <div className="mb-1.5 flex items-center gap-2">
                  <span className="rounded-md bg-white/5 px-1.5 py-0.5 font-mono text-[11px] text-slate-400">#{i + 1}</span>
                  <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold ${m.cls}`}>{m.icon}{m.label}</span>
                  {e.data.model_ms != null && <span className="ml-auto font-mono text-[10.5px] text-slate-500">{secs(e.data.model_ms)}</span>}
                </div>
                <p className="text-[13px] leading-relaxed text-slate-200">{e.message}</p>
                {e.data.actions && e.data.actions.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {e.data.actions.map((a, j) => (
                      <span key={j} className="rounded-md bg-white/5 px-1.5 py-0.5 font-mono text-[11px] text-slate-300">{a.action} {a.ref}{a.value_key && <span className="text-violet-300"> ← {a.value_key}</span>}</span>
                    ))}
                  </div>
                )}
              </motion.article>
            );
          })}
        </AnimatePresence>
      </div>
    </section>
  );
}

function ResultCard({ r }: { r: Receipt }) {
  const [verified, setVerified] = useState<boolean | null>(null);
  const [raw, setRaw] = useState(false);
  const toast = useToast();
  const res = r.result;
  return (
    <motion.section initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="overflow-hidden rounded-2xl bg-white text-slate-900 shadow-2xl shadow-black/30">
      <div className="tricolor-bar h-1" />
      <div className="grid gap-6 p-5 lg:grid-cols-[1.4fr_1fr]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="grid size-10 place-items-center rounded-xl bg-leaf-50 text-leaf-700"><CircleCheck className="size-6" /></span>
            <h2 className="text-2xl font-extrabold text-navy-900">
              {r.outcome === "submitted" ? "Filed, with your approval" : r.outcome === "information_retrieved" ? (res?.count === 0 ? "The portal found no matching schemes" : "Here is what the portal found") : "Dry run complete"}
            </h2>
          </div>
          {r.reference_no && (
            <div className="mt-4 rounded-2xl bg-navy-50 p-4">
              <div className="text-xs font-bold uppercase tracking-wider text-navy-500">Reference number from the portal</div>
              <div className="mt-1 flex items-center gap-2 font-mono text-2xl font-bold text-navy-900">
                {r.reference_no}
                <button aria-label="Copy reference number" className="rounded-lg p-1.5 hover:bg-white" onClick={() => { navigator.clipboard.writeText(r.reference_no!); toast("ok", "Copied"); }}><Copy className="size-4" /></button>
              </div>
            </div>
          )}
          {res && res.items.length > 0 && (
            <>
              <p className="mt-3 text-sm text-slate-600">{res.count != null && res.count > res.items.length ? `${res.count} schemes matched; the first ${res.items.length} are listed by the portal.` : `${res.items.length} matched.`}</p>
              <ol className="mt-3 grid gap-2 sm:grid-cols-2">
                {res.items.map((it, i) => (
                  <motion.li key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
                    <a href={it.url ?? "#"} target="_blank" rel="noopener noreferrer" className="group flex h-full items-start gap-3 rounded-xl p-3 ring-1 ring-navy-100 transition hover:bg-saffron-50 hover:ring-saffron-200">
                      <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-saffron-100 text-xs font-bold text-saffron-700">{i + 1}</span>
                      <span className="flex-1 text-sm font-semibold text-navy-900 group-hover:underline">{it.title}</span>
                      <ExternalLink className="size-4 shrink-0 text-slate-400" />
                    </a>
                  </motion.li>
                ))}
              </ol>
            </>
          )}
          {res && <p className="mt-3 text-xs text-slate-500">Read live from {new URL(res.source_url).hostname} at {new Date(res.retrieved_at).toLocaleString()}. Listed by the portal, not written by the AI.</p>}
        </div>
        <div className="space-y-3">
          <div className="rounded-2xl bg-slate-50 p-4 text-sm">
            <div className="mb-2 flex items-center gap-2 font-semibold text-navy-900"><ScrollText className="size-4" />Signed receipt</div>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-slate-600">
              <dt>Receipt</dt><dd className="truncate font-mono text-xs text-slate-800">{r.receipt_id}</dd>
              <dt>Key</dt><dd className="font-mono text-xs text-slate-800">{r.signer_key_id}</dd>
              <dt>Evidence</dt><dd>{r.evidence.length} hashed files</dd>
              <dt>Agent time</dt><dd>{secs(r.timing.agent_ms)} · {r.timing.model_calls ?? 0} AI calls</dd>
            </dl>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button variant="secondary" className="!min-h-9 !px-3 text-sm" onClick={async () => setVerified((await api.verify(r)).valid)}><BadgeCheck className="size-4" />Verify signature</Button>
              {verified != null && (verified
                ? <span className="inline-flex items-center gap-1 text-sm font-semibold text-leaf-700"><ShieldCheck className="size-4" />Unchanged since issued</span>
                : <span className="text-sm font-semibold text-red-700">Signature does not match</span>)}
            </div>
            <p className="mt-2 text-xs text-slate-500">A valid signature proves this record was not altered. It does not prove the portal accepted anything.</p>
          </div>
          <button className="text-sm font-semibold text-navy-700 underline-offset-2 hover:underline" onClick={() => setRaw(!raw)}>{raw ? "Hide" : "Show"} extracted data (JSON)</button>
          {raw && <pre className="max-h-64 overflow-auto rounded-xl bg-night-900 p-3 font-mono text-[11px] leading-relaxed text-emerald-200">{JSON.stringify({ outcome: r.outcome, reference_no: r.reference_no, result: r.result, evidence: r.evidence, timing: r.timing }, null, 2)}</pre>}
        </div>
      </div>
    </motion.section>
  );
}

function ApprovalSheet({ s, taskId, token }: { s: TaskState; taskId: string; token: string }) {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const card = s.card!;
  const decide = async (d: "approved" | "rejected") => {
    setBusy(d);
    try { await api.approve(taskId, token, d); toast(d === "approved" ? "ok" : "warn", d === "approved" ? "Approved. Submitting once." : "Rejected. Nothing was submitted."); }
    catch (e) { toast("error", (e as Error).message); setBusy(null); }
  };
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-end justify-center bg-black/55 p-3 sm:items-center" role="dialog" aria-modal aria-labelledby="approve-title">
      <motion.div initial={{ y: 40, scale: 0.98 }} animate={{ y: 0, scale: 1 }} exit={{ y: 30, opacity: 0 }} transition={{ type: "spring", stiffness: 260, damping: 26 }}
        className="max-h-[92dvh] w-full max-w-2xl overflow-y-auto rounded-3xl bg-white text-slate-900 shadow-2xl">
        <div className="tricolor-bar h-1.5" />
        <div className="p-5 sm:p-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-saffron-700">Check before anything is filed</p>
              <h2 id="approve-title" className="text-2xl font-extrabold text-navy-900">Approve this submission?</h2>
              <p className="mt-1 text-sm text-slate-600">{card.portal.name} · {card.service}</p>
            </div>
            {card.portal.is_sandbox && <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-800">Sandbox replica</span>}
          </div>
          <dl className="mt-4 divide-y divide-slate-100 rounded-2xl ring-1 ring-slate-100">
            {card.values.map((v, i) => (
              <div key={i} className="grid grid-cols-[40%_1fr] gap-3 px-4 py-2.5 text-sm">
                <dt className="text-slate-500">{v.label}</dt>
                <dd className="font-medium text-slate-900">{v.value}{!v.readback_ok && <span className="ml-2 text-xs font-semibold text-amber-700">⚠ check</span>}</dd>
              </div>
            ))}
            {card.documents.map((d) => (
              <div key={d.key} className="grid grid-cols-[40%_1fr] gap-3 px-4 py-2.5 text-sm"><dt className="text-slate-500">Document: {d.key}</dt><dd>{d.size_kb} KB · {d.note}</dd></div>
            ))}
          </dl>
          {[...card.differences.map((d) => ({ t: d, w: false })), ...card.warnings.map((w) => ({ t: w, w: true }))].map((x, i) => (
            <p key={i} className={`mt-3 flex items-start gap-2 rounded-xl p-3 text-sm ${x.w ? "bg-rose-50 text-rose-800" : "bg-amber-50 text-amber-900"}`}>{x.w ? <ShieldAlert className="mt-0.5 size-4 shrink-0" /> : <CircleAlert className="mt-0.5 size-4 shrink-0" />}{x.t}</p>
          ))}
          <img src={`/citizen/${taskId}/approval.png?t=${encodeURIComponent(token)}`} alt="Screenshot of the portal's final review page" className="mt-4 w-full rounded-2xl ring-1 ring-slate-200" />
          <p className="mt-4 text-sm text-slate-700">{card.next}</p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Button variant="saffron" loading={busy === "approved"} disabled={!!busy} onClick={() => decide("approved")}><CircleCheck className="size-5" />Approve and submit</Button>
            <Button variant="ghost" className="!text-red-700" disabled={!!busy} onClick={() => decide("rejected")}><X className="size-5" />Reject</Button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

// ------------------------------------------------------------------ page
export default function AgentRoom() {
  const { taskId = "" } = useParams();
  const [params] = useSearchParams();
  const token = params.get("t") ?? "";
  const [s, setS] = useState<TaskState | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let stop = false, timer: number | undefined;
    const tick = async () => {
      try {
        const next = await api.task(taskId, token);
        if (stop) return;
        setS(next); setErr(null);
        if (TERMINAL.has(next.status)) return;
      } catch (e) { if (!stop) setErr((e as Error).message); }
      timer = window.setTimeout(tick, 900);
    };
    tick();
    return () => { stop = true; clearTimeout(timer); };
  }, [taskId, token]);

  const lines = useMemo(() => {
    if (!s) return [];
    const t0 = s.events.length ? new Date(s.events[0].at).getTime() : 0;
    return s.events.map((e) => lineFor(e, t0, s.portal.name)).filter((l): l is Line => !!l && !(l.text.startsWith("Not done yet")));
  }, [s]);
  const caption = useMemo(() => [...lines].reverse().find((l) => l.tone === "info" || l.tone === "ai") ?? null, [lines]);

  if (err && !s) {
    return <div className="mx-auto max-w-xl px-4 py-24 text-center"><CircleAlert className="mx-auto size-10 text-rose-300" /><p className="mt-3 text-lg text-slate-200">This task link is not valid.</p><Link to="/agent" className="mt-4 inline-block text-amber-300 underline">Start a new task</Link></div>;
  }
  if (!s) return <div className="grid min-h-[60vh] place-items-center"><LoaderCircle className="size-10 animate-spin text-amber-300" aria-label="Loading" /></div>;

  const t = s.timing;
  return (
    <div className="mx-auto max-w-[96rem] px-4 py-5">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Link to="/agent" className="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm text-slate-400 hover:bg-white/5 hover:text-white"><ArrowLeft className="size-4" />Agent room</Link>
        <span className="rounded-lg bg-white/5 px-2.5 py-1 font-mono text-xs text-slate-300 ring-1 ring-white/10">{s.task_id}</span>
        <StatusBadge status={s.status} />
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${s.portal.is_sandbox ? "bg-amber-400/15 text-amber-200" : "bg-emerald-400/15 text-emerald-200"}`}>
          {s.portal.is_sandbox ? "Sandbox replica" : "Live government portal"} · {s.portal.name}
        </span>
        <span className="rounded-full bg-violet-400/15 px-2.5 py-0.5 text-xs font-semibold text-violet-200">{s.strategy === "explore" ? "AI exploring live" : "Replaying learned route"}</span>
        <div className="ml-auto flex flex-wrap gap-2 text-xs">
          {[["Agent", secs(t.agent_ms), <Timer key="a" className="size-3.5" />], ["Waiting for you", secs(t.human_wait_ms), <Hand key="h" className="size-3.5" />], ["AI calls", String(t.model_calls ?? 0), <BrainCircuit key="m" className="size-3.5" />]].map(([k, v, icon]) => (
            <span key={k as string} className="inline-flex items-center gap-1.5 rounded-lg bg-white/5 px-2.5 py-1.5 text-slate-300 ring-1 ring-white/10">{icon}{k}<b className="font-mono text-white">{v}</b></span>
          ))}
        </div>
      </div>

      <div className="mb-4"><Pipeline s={s} /></div>

      {(s.status === "failed" || s.status === "needs_review") && (
        <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} className="mb-4 flex items-start gap-3 rounded-2xl bg-rose-500/10 p-4 text-rose-100 ring-1 ring-rose-400/30">
          <ShieldAlert className="mt-0.5 size-5 shrink-0 text-rose-300" />
          <div><p className="font-semibold">Stopped safely: nothing was guessed or submitted twice.</p><p className="mt-1 text-sm text-rose-200/90">{s.error}</p></div>
        </motion.div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-[minmax(0,21rem)_minmax(0,1fr)_minmax(0,21rem)]">
        <div className="order-2 2xl:order-1"><Activity lines={lines} s={s} /></div>
        <div className="order-1 lg:col-span-2 2xl:order-2 2xl:col-span-1"><BrowserCard s={s} taskId={taskId} token={token} caption={caption} /></div>
        <div className="order-3"><Reasoning s={s} /></div>
      </div>

      {s.receipt && <div className="mt-6"><ResultCard r={s.receipt} /></div>}

      <AnimatePresence>{s.approval_pending && s.card && <ApprovalSheet s={s} taskId={taskId} token={token} />}</AnimatePresence>
    </div>
  );
}
