import { AnimatePresence, motion } from "motion/react";
import { ArrowUpRight, BookOpenCheck, Landmark, LoaderCircle, MessageCircleQuestion, Scale, Send, ShieldAlert, X } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { civicGuide, type CivicGuideAnswer } from "../api";

const PROMPTS = [
  "My bank is pressuring me about a loan repayment. What official options should I check?",
  "How do I verify a land record before buying property?",
  "I received a suspicious UPI payment message. What should I do?",
  "How can I understand a tax notice I received?",
];

const TOPIC_ICON = { "Banking & loans": Landmark, "Land & property": Scale } as const;
type ActivitySummary = { completed: number; week: number; saved: number };

function answerBlocks(text: string) {
  return text.split(/\n{2,}/).filter(Boolean);
}

export function CivicGuideChat({ activity }: { activity: ActivitySummary | null }) {
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState<CivicGuideAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLTextAreaElement>(null);

  async function ask(event?: FormEvent, scope: "auto" | "civic" | "portal" = "auto", questionOverride?: string) {
    event?.preventDefault();
    const question = (questionOverride ?? message).trim();
    if (question.length < 12 || busy) return;
    setBusy(true); setError(null); setAnswer(null);
    try {
      setAnswer(await civicGuide.ask(question, "English", scope));
    } catch (err) {
      setError(err instanceof Error ? err.message : "The guide could not answer right now. Please try again.");
    } finally { setBusy(false); }
  }

  const Icon = answer ? (TOPIC_ICON[answer.category as keyof typeof TOPIC_ICON] ?? BookOpenCheck) : MessageCircleQuestion;
  return (
    <section className="mt-6 overflow-hidden rounded-[2rem] bg-gradient-to-br from-navy-900 via-navy-800 to-[#143966] p-5 text-white shadow-[0_24px_55px_-28px_rgb(19_48_107/.75)] sm:p-7" aria-labelledby="civic-guide-title">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(280px,.85fr)] lg:items-start">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full bg-leaf-500/20 px-3 py-1 text-xs font-bold uppercase tracking-[.15em] text-leaf-100 ring-1 ring-leaf-500/30"><BookOpenCheck className="size-3.5" />Official-source guide</span>
          <h1 id="civic-guide-title" className="mt-3 text-2xl font-extrabold sm:text-3xl">What do you need help with?</h1>
          <p className="mt-2 max-w-xl text-sm leading-6 text-navy-100 sm:text-base">Choose a guide for life, work, money or rights — or ask how to use Swayam-sevak. We will point you to a clear next step.</p>
          <form onSubmit={ask} className="mt-5 rounded-2xl bg-white p-2 shadow-lg ring-1 ring-white/20">
            <label htmlFor="civic-guide-question" className="sr-only">Your civic question</label>
            <textarea ref={input} id="civic-guide-question" value={message} onChange={(event) => setMessage(event.target.value)} maxLength={1200} rows={3}
              placeholder="For example: My lender called my family about an overdue EMI. What can I verify and where can I complain?"
              className="w-full resize-none rounded-xl bg-transparent px-3 py-2 text-sm leading-6 text-navy-900 outline-none placeholder:text-slate-400" />
            <div className="flex flex-col gap-2 border-t border-navy-100 px-2 pt-2 sm:flex-row sm:items-center sm:justify-between">
              <span className="flex items-start gap-1.5 text-xs leading-5 text-slate-500"><ShieldAlert className="mt-0.5 size-3.5 shrink-0 text-saffron-600" />Never share Aadhaar, account/card numbers, passwords or OTPs.</span>
              <button type="submit" disabled={busy || message.trim().length < 12} className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-xl bg-saffron-500 px-4 text-sm font-extrabold text-navy-900 transition hover:bg-saffron-400 disabled:cursor-not-allowed disabled:opacity-50">
                {busy ? <LoaderCircle className="size-4 animate-spin" /> : <Send className="size-4" />}{busy ? "Checking sources…" : "Ask guide"}
              </button>
            </div>
          </form>
          <div className="mt-3 flex flex-wrap gap-2" aria-label="Example questions">
            {PROMPTS.map((prompt) => <button key={prompt} type="button" onClick={() => { setMessage(prompt); input.current?.focus(); }} className="rounded-full bg-white/10 px-3 py-1.5 text-left text-xs font-semibold text-navy-100 ring-1 ring-white/15 transition hover:bg-white/20">{prompt}</button>)}
            <button type="button" onClick={() => { const question = "How do I use Swayam-sevak and which page should I open?"; setMessage(question); void ask(undefined, "portal", question); }} className="rounded-full bg-saffron-400/20 px-3 py-1.5 text-left text-xs font-bold text-saffron-100 ring-1 ring-saffron-300/30 transition hover:bg-saffron-400/30">Guide me around this website</button>
          </div>
        </div>

        <div className="relative flex min-h-[12rem] flex-col overflow-hidden rounded-3xl bg-white/10 p-4 ring-1 ring-white/15">
          <div className="pointer-events-none absolute -right-12 -top-14 size-44 rounded-full border-[22px] border-saffron-400/20" />
          <div className="pointer-events-none absolute -bottom-14 -left-10 size-32 rounded-full border-[18px] border-leaf-500/20" />
          <AnimatePresence mode="wait">
            {!answer && !error && <motion.div key="intro" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="relative flex min-h-[10rem] flex-1 flex-col justify-center">
              <span className="grid size-12 place-items-center rounded-2xl bg-saffron-400 text-navy-900 shadow-lg"><MessageCircleQuestion className="size-6" /></span>
              <p className="mt-4 text-lg font-extrabold">Tell us what you want to do.</p><p className="mt-1 text-sm leading-6 text-navy-100">Get help with this website, understand a civic issue, or find the official place to start.</p>
            </motion.div>}
            {busy && <motion.div key="busy" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="relative flex min-h-[10rem] flex-col justify-center"><LoaderCircle className="size-8 animate-spin text-saffron-300" /><p className="mt-4 font-bold">Finding official sources…</p><p className="mt-1 text-sm text-navy-100">No answer is generated until the source check is complete.</p></motion.div>}
            {error && <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="relative min-h-[10rem]"><button type="button" onClick={() => setError(null)} className="float-right rounded-lg p-1 text-navy-100 hover:bg-white/10" aria-label="Dismiss error"><X className="size-4" /></button><ShieldAlert className="size-7 text-saffron-300" /><p className="mt-3 font-bold">No reliable answer yet</p><p className="mt-1 text-sm leading-6 text-navy-100">{error}</p></motion.div>}
            {answer && <motion.div key="answer" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="relative"><div className="flex items-center justify-between gap-3"><span className="inline-flex items-center gap-2 text-sm font-extrabold"><Icon className="size-4 text-saffron-300" />{answer.category}</span><button type="button" onClick={() => { setAnswer(null); input.current?.focus(); }} className="rounded-lg p-1 text-navy-100 hover:bg-white/10" aria-label="Close answer"><X className="size-4" /></button></div><div className="mt-3 max-h-64 space-y-2 overflow-y-auto pr-1 text-sm leading-6 text-white" aria-live="polite">{answerBlocks(answer.answer).map((block, index) => <p key={index}>{block}</p>)}</div><p className="mt-3 border-t border-white/15 pt-3 text-xs leading-5 text-navy-100">{answer.disclaimer}</p></motion.div>}
          </AnimatePresence>
          <dl className="relative mt-4 grid grid-cols-3 gap-2 border-t border-white/15 pt-3" aria-label="Your Swayam-sevak activity">
            {[
              [activity?.completed, "actions recorded"],
              [activity?.week, "this week"],
              [activity?.saved, "saved updates"],
            ].map(([value, label]) => (
              <div key={String(label)} className="rounded-xl bg-night-950/25 px-2 py-2 text-center ring-1 ring-white/10">
                <dd className="font-display text-2xl font-extrabold tabular-nums text-white">{value ?? "—"}</dd>
                <dt className="mt-0.5 text-[11px] font-semibold leading-4 text-navy-100">{label}</dt>
              </div>
            ))}
          </dl>
          <p className="relative mt-2 text-right text-[11px] text-navy-100">From your private activity history</p>
        </div>
      </div>
      {answer && (answer.sources.length > 0 || answer.actions.length > 0 || answer.support) && <div className="mt-5 border-t border-white/15 pt-4">
        {answer.sources.length > 0 && <><p className="text-xs font-bold uppercase tracking-[.14em] text-saffron-200">Official sources checked</p><div className="mt-2 grid gap-2 sm:grid-cols-3">{answer.sources.map((source) => <a key={source.url} href={source.url} target="_blank" rel="noreferrer" className="group rounded-2xl bg-white/10 p-3 text-sm ring-1 ring-white/10 transition hover:bg-white/15"><span className="line-clamp-2 font-bold text-white">{source.title}</span><span className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-saffron-200">Open official page <ArrowUpRight className="size-3 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5" /></span></a>)}</div></>}
        {answer.actions.length > 0 && <><p className="mt-4 text-xs font-bold uppercase tracking-[.14em] text-saffron-200">Take me there</p><div className="mt-2 flex flex-wrap gap-2">{answer.actions.map((action) => <Link key={action.path} to={action.path} className="inline-flex min-h-9 items-center rounded-xl bg-white px-3 text-sm font-bold text-navy-800 transition hover:bg-navy-50">{action.label}<ArrowUpRight className="ml-1.5 size-3.5" /></Link>)}</div></>}
        {answer.support && <p className="mt-4 text-xs leading-5 text-navy-100">Verified support: {answer.support.phone ?? answer.support.email ?? answer.support.url}</p>}
      </div>}
    </section>
  );
}
