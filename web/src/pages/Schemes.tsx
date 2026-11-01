import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, BookOpen, CircleCheck, CircleX, ExternalLink, Info, LoaderCircle, Mic, Pause, Search, Square, Volume2, Workflow } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type AppConfig, type Service } from "../api";
import { SchemesArt } from "../components/Illustrations";
import { ServiceForm } from "../components/ServiceForm";
import { Badge, Button, Card, fadeUp, NotConnected, SectionTitle, stagger, useToast } from "../components/ui";

const LANGS = [
  { code: "en-IN", label: "English" }, { code: "hi-IN", label: "हिन्दी" }, { code: "ta-IN", label: "தமிழ்" },
  { code: "bn-IN", label: "বাংলা" }, { code: "mr-IN", label: "मराठी" }, { code: "te-IN", label: "తెలుగు" },
];

/** Part 1 contract: POST /api/explain {question, language} -> Explanation (see docs/UI_CONTRACT.md). */
type Explanation = {
  answer: string;
  citations?: { title: string; reference?: string; date?: string; url?: string }[];
  eligibility?: { criterion: string; met: boolean | null; note?: string }[];
  audio_url?: string;
  apply?: { portal_id: string; service_id: string; label?: string };
};

function useSpeechInput(lang: string, onText: (t: string) => void) {
  const [listening, setListening] = useState(false);
  const rec = useRef<any>(null);
  const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  const start = () => {
    if (!SR) return false;
    const r = new SR();
    r.lang = lang; r.interimResults = false; r.maxAlternatives = 1;
    r.onresult = (e: any) => onText(e.results[0][0].transcript);
    r.onend = () => setListening(false);
    r.onerror = () => setListening(false);
    rec.current = r; r.start(); setListening(true);
    return true;
  };
  const stop = () => { rec.current?.stop(); setListening(false); };
  return { supported: !!SR, listening, start, stop };
}

function VoiceExplainer({ text, lang, audioUrl }: { text: string; lang: string; audioUrl?: string }) {
  const [playing, setPlaying] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  useEffect(() => () => { speechSynthesis.cancel(); audio.current?.pause(); }, []);
  const toggle = () => {
    if (playing) { speechSynthesis.cancel(); audio.current?.pause(); setPlaying(false); return; }
    if (audioUrl) {
      audio.current = new Audio(audioUrl); audio.current.onended = () => setPlaying(false); audio.current.play(); setPlaying(true); return;
    }
    const u = new SpeechSynthesisUtterance(text); u.lang = lang; u.rate = 0.95; u.onend = () => setPlaying(false);
    speechSynthesis.speak(u); setPlaying(true);
  };
  return (
    <button onClick={toggle} className="group flex items-center gap-3 rounded-2xl bg-navy-700 px-4 py-3 text-left text-white shadow-lg hover:bg-navy-800" aria-pressed={playing}>
      <span className="grid size-10 place-items-center rounded-full bg-saffron-500 text-navy-900">{playing ? <Pause className="size-5" /> : <Volume2 className="size-5" />}</span>
      <span>
        <span className="block text-sm font-bold">{playing ? "Playing…" : "Listen to this"}</span>
        <span className="flex h-4 items-end gap-0.5" aria-hidden>
          {Array.from({ length: 18 }).map((_, i) => (
            <motion.span key={i} className="w-1 rounded-full bg-saffron-300" animate={playing ? { height: [4, 6 + ((i * 7) % 10), 4] } : { height: 4 }}
              transition={{ duration: 0.6 + (i % 4) * 0.12, repeat: playing ? Infinity : 0 }} />
          ))}
        </span>
      </span>
    </button>
  );
}

function AnswerPanel({ ex, lang }: { ex: Explanation; lang: string }) {
  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
      <Card variant="plain" className="p-6">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-xl font-extrabold text-navy-900">What this means for you</h3>
          <VoiceExplainer text={ex.answer} lang={lang} audioUrl={ex.audio_url} />
        </div>
        <p className="whitespace-pre-line text-lg leading-relaxed text-slate-800">{ex.answer}</p>
        {ex.citations && ex.citations.length > 0 && (
          <div className="mt-5 border-t border-slate-100 pt-4">
            <p className="mb-2 text-sm font-bold text-navy-700">Official sources</p>
            <ul className="space-y-2">
              {ex.citations.map((c, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <BookOpen className="mt-0.5 size-4 shrink-0 text-saffron-700" />
                  <span>
                    {c.url ? <a href={c.url} target="_blank" rel="noopener noreferrer" className="font-semibold text-navy-700 underline-offset-2 hover:underline">{c.title}</a> : <b>{c.title}</b>}
                    {(c.reference || c.date) && <span className="text-slate-500"> · {[c.reference, c.date].filter(Boolean).join(" · ")}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>
      {ex.eligibility && ex.eligibility.length > 0 && (
        <Card variant="clay" className="p-6">
          <h3 className="text-xl font-extrabold text-navy-900">Your eligibility</h3>
          <ul className="mt-3 space-y-2">
            {ex.eligibility.map((e, i) => (
              <li key={i} className="flex items-start gap-2">
                {e.met ? <CircleCheck className="mt-0.5 size-5 shrink-0 text-leaf-600" /> : e.met === false ? <CircleX className="mt-0.5 size-5 shrink-0 text-red-600" /> : <Info className="mt-0.5 size-5 shrink-0 text-slate-400" />}
                <span><span className="font-semibold text-slate-900">{e.criterion}</span>{e.note && <span className="block text-sm text-slate-600">{e.note}</span>}</span>
              </li>
            ))}
          </ul>
          {ex.apply && (
            <Link to={`/agent?service=${ex.apply.portal_id}/${ex.apply.service_id}`} className="mt-5 block">
              <Button variant="saffron" className="w-full">{ex.apply.label ?? "Apply with the agent"}<ArrowRight className="size-4" /></Button>
            </Link>
          )}
        </Card>
      )}
    </motion.div>
  );
}

export default function Schemes() {
  const toast = useToast();
  const [searchParams] = useSearchParams();
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [finder, setFinder] = useState<Service | null>(null);
  const initialLanguage = searchParams.get("lang");
  const [q, setQ] = useState(() => searchParams.get("q") ?? "");
  const [lang, setLang] = useState(() => LANGS.some((item) => item.code === initialLanguage) ? initialLanguage! : "hi-IN");
  const [busy, setBusy] = useState(false);
  const [ex, setEx] = useState<Explanation | null>(null);
  const [notConnected, setNotConnected] = useState(false);
  const speech = useSpeechInput(lang, (t) => setQ((x) => (x ? `${x} ${t}` : t)));

  useEffect(() => {
    api.config().then(setConfig).catch(() => {});
    api.services().then((s) => setFinder(s.find((x) => x.portal_id === "myscheme" && x.service_id === "find_schemes") ?? null)).catch(() => {});
  }, []);

  async function ask(e: FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    if (!config?.part1_connected) { setNotConnected(true); setEx(null); return; }
    setBusy(true); setNotConnected(false);
    try {
      setEx(await api.part1("api/explain", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: q, language: lang }) }));
    } catch (err) { toast("error", (err as Error).message); }
    setBusy(false);
  }

  return (
    <div>
      <section className="mx-auto grid max-w-7xl items-center gap-10 px-4 pb-10 pt-10 lg:grid-cols-[1.2fr_1fr]">
        <motion.div initial="hidden" animate="show" variants={stagger}>
          <motion.div variants={fadeUp}><Badge tone="leaf">Part 1 · Rights & schemes explainer</Badge></motion.div>
          <motion.h1 variants={fadeUp} className="mt-4 text-4xl font-extrabold leading-tight text-navy-900 sm:text-5xl">Know your rights, in your language.</motion.h1>
          <motion.p variants={fadeUp} className="mt-4 max-w-xl text-lg text-slate-700">Ask about any scheme or government notice. You get a plain answer with the official source, your eligibility, and a voice you can listen to.</motion.p>
          <motion.form variants={fadeUp} onSubmit={ask} className="glass mt-7 rounded-3xl p-3">
            <label htmlFor="q" className="sr-only">Your question</label>
            <div className="flex items-center gap-2">
              <Search className="ml-2 size-5 shrink-0 text-navy-400" aria-hidden />
              <input id="q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. क्या मुझे छात्रवृत्ति मिल सकती है? / Can I get a scholarship?"
                className="min-h-12 flex-1 bg-transparent text-base text-slate-900 outline-none placeholder:text-slate-400" />
              {speech.supported && (
                <button type="button" onClick={() => (speech.listening ? speech.stop() : speech.start())} aria-label={speech.listening ? "Stop listening" : "Speak your question"}
                  className={`grid size-11 place-items-center rounded-xl ${speech.listening ? "pulse-ring bg-saffron-500 text-navy-900" : "bg-navy-50 text-navy-700 hover:bg-navy-100"}`}>
                  {speech.listening ? <Square className="size-4" /> : <Mic className="size-5" />}
                </button>
              )}
              <Button type="submit" loading={busy} className="!rounded-2xl">Ask</Button>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5 px-2 pb-1">
              {LANGS.map((l) => (
                <button type="button" key={l.code} onClick={() => setLang(l.code)}
                  className={`rounded-full px-3 py-1 text-sm font-semibold ${lang === l.code ? "bg-navy-700 text-white" : "bg-white text-navy-700 ring-1 ring-navy-100 hover:ring-navy-300"}`}>{l.label}</button>
              ))}
            </div>
          </motion.form>
          <Link to="/schemes/engine" className="mt-4 inline-flex items-center gap-1.5 text-sm font-bold text-navy-700 hover:text-saffron-700"><Workflow className="size-4" />See how answers are made (the engine room)</Link>
        </motion.div>
        <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.45 }}>
          <Card variant="clay" className="bg-white p-6"><SchemesArt className="h-auto w-full" title="A citizen reading about her rights in Hindi and English" /></Card>
        </motion.div>
      </section>

      <section className="mx-auto max-w-7xl px-4">
        <AnimatePresence mode="wait">
          {busy && <motion.div key="busy" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="relative overflow-hidden rounded-3xl bg-white p-6 ring-1 ring-navy-100"><div className="shimmer absolute inset-0" /><p className="flex items-center gap-2 font-semibold text-navy-800"><LoaderCircle className="size-5 animate-spin" />Reading the official documents…</p></motion.div>}
          {ex && !busy && <AnswerPanel key="ans" ex={ex} lang={lang} />}
          {notConnected && !busy && (
            <motion.div key="nc" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
              <NotConnected part="The explainer (Part 1)" endpoint="PART1_API_URL" what="It reads government notifications and answers your question with sources and a voice explainer. Meanwhile, the live scheme finder below already works." />
            </motion.div>
          )}
        </AnimatePresence>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-14" aria-labelledby="finder">
        <SectionTitle kicker="Live from myScheme.gov.in" title="Find schemes for me">
          Answer the official questionnaire once. Our agent fills it on the real myScheme portal and brings back the matching schemes, with links to the official pages.
        </SectionTitle>
        <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
          <Card variant="plain" className="p-5 sm:p-7">
            {finder ? <ServiceForm service={finder} submitLabel="Find my schemes" /> : <p className="flex items-center gap-2 text-slate-500"><LoaderCircle className="size-4 animate-spin" />Loading the questionnaire…</p>}
          </Card>
          <aside className="space-y-4">
            {[
              { n: "1", t: "You answer", b: "About 10 questions. Your PIN code fills your state." },
              { n: "2", t: "The agent fills myScheme", b: "Six screens on the real portal, in about 4 seconds. You can watch it live." },
              { n: "3", t: "You get the list", b: "The portal's own results, with links. Nothing is invented by AI." },
            ].map((s) => (
              <Card key={s.n} variant="glass" className="flex gap-3 p-4">
                <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-saffron-500 font-bold text-navy-900">{s.n}</span>
                <div><div className="font-bold text-navy-900">{s.t}</div><p className="text-sm text-slate-600">{s.b}</p></div>
              </Card>
            ))}
          </aside>
        </div>
      </section>
    </div>
  );
}
