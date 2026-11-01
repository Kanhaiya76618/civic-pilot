import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, BookOpen, Bot, CalendarClock, CircleCheck, CircleX, ClipboardPaste, ExternalLink, FileUp, Info, Link2, Languages, ListChecks, LoaderCircle, Mic, Pause, Scale, ScanText, Search, ShieldCheck, Square, Store, UserCheck, Users, Volume2, Workflow } from "lucide-react";
import { createContext, useContext, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, remember, type AppConfig, type Service } from "../api";
import { ServiceForm } from "../components/ServiceForm";
import { Badge, Button, Card, fadeUp, NotConnected, SectionTitle, stagger, useToast } from "../components/ui";

const LANGS = [
  { code: "hi-IN", label: "हिन्दी" }, { code: "en-IN", label: "English" }, { code: "bn-IN", label: "বাংলা" }, { code: "ta-IN", label: "தமிழ்" },
  { code: "te-IN", label: "తెలుగు" }, { code: "mr-IN", label: "मराठी" }, { code: "gu-IN", label: "ગુજરાતી" }, { code: "kn-IN", label: "ಕನ್ನಡ" },
  { code: "ml-IN", label: "മലയാളം" }, { code: "pa-IN", label: "ਪੰਜਾਬੀ" }, { code: "or-IN", label: "ଓଡ଼ିଆ" }, { code: "ur-IN", label: "اردو" },
];

// Real official documents, to try it quickly. Any .gov.in / .nic.in link, PDF or pasted text works the same way.
const SAMPLES = [
  { label: "Disability pension (myScheme page)", url: "https://www.myscheme.gov.in/schemes/igndps" },
  { label: "PMSBY accident insurance rules (PDF)", url: "https://jansuraksha.gov.in/Files/PMSBY/English/Rules.pdf" },
];

type Point = { text: string; quote: string; page: number | null };
type Doc = { doc_id: string; title: string; url: string | null; chars: number; page_count: number; source: string };
/** Part 1, built in (executor/explainer.py): every point carries a quote that was checked against the document. */
type Explanation = {
  language: string; question: string; title: string; summary: string; answer: string;
  doc: { doc_id: string; title: string; url: string | null; issuer: string | null; date: string | null; doc_type: string | null; page_count: number;
         ocr?: { pages_read: number; pages_total: number; reason?: "scanned" | "indian_script" } | null };
  rights: Point[]; impacts: { citizens: Point[]; business: Point[] }; deadlines: Point[]; how_to_act: Point[];
  eligibility: { criterion: string; met: boolean | null; note?: string; quote?: string; page?: number | null }[];
  citations?: { title: string; reference?: string; date?: string; url?: string }[];
  voice_script: string; audio_url?: string | null; voice_provider: string;
  language_from_question?: boolean; dropped_unverified: number; untranslated: number; timing?: { ms: number; ai_calls: number }; cached?: boolean; labels?: Partial<Labels>;
  apply?: { portal_id: string; service_id: string; label?: string; description?: string } | null;
};
type Stage = { id: string; status: string; ms?: number; note?: string };

// Headings come back translated with the answer; these are the English fallbacks.
const LABELS = {
  your_question: "Your question", in_short: "In short", rights: "Your rights", eligible: "Who is eligible",
  citizens: "What changes for citizens", business: "What changes for small businesses", deadlines: "Dates and deadlines",
  what_to_do: "What to do", from_document: "From the document", page: "page", listen: "Listen to this", playing: "Playing…",
  no_rights: "The document states no specific rights.", no_business: "This document does not affect shops, MSMEs or employers.",
  checked: "Every point above quotes the document, and each quote was checked against its text.",
};
type Labels = typeof LABELS;
const LabelsCtx = createContext<Labels>(LABELS);
const useL = () => useContext(LabelsCtx);
const STAGE_LABEL: Record<string, string> = {
  ingest: "Reading", parse: "Text", chunk: "Pieces", embed: "Embed", retrieve: "Relevant parts", reason: "Explaining", translate: "Translating", voice: "Voice",
};

/** Records a spoken question in the page (works on Android, iPhone and desktop browsers) and turns it into text on the
 * server (Whisper via AIML API). Without a chosen language the server detects it, and the answer then follows it. */
function useVoiceQuestion(lang: string | null, onText: (text: string, language: string | null) => void, onError: (m: string) => void) {
  const [state, setState] = useState<"idle" | "recording" | "transcribing">("idle");
  const [seconds, setSeconds] = useState(0);
  const rec = useRef<MediaRecorder | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const supported = typeof window !== "undefined" && "MediaRecorder" in window && !!navigator.mediaDevices?.getUserMedia;

  async function start() {
    let stream: MediaStream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
    catch { onError("Microphone permission is needed to ask by voice."); return; }
    const chunks: Blob[] = [];
    const r = new MediaRecorder(stream);
    r.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    r.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      clearInterval(timer.current);
      const blob = new Blob(chunks, { type: r.mimeType || "audio/webm" });
      if (blob.size < 1000) { setState("idle"); return; }
      setState("transcribing");
      const fd = new FormData();
      fd.append("audio", blob, "question");
      if (lang) fd.append("language", lang);
      try {
        const res = await fetch("/app/part1/api/transcribe", { method: "POST", body: fd });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Could not understand the recording");
        if (body.text) onText(body.text, body.language ?? null); else onError("No speech was heard. Please try again.");
      } catch (e) { onError((e as Error).message); }
      setState("idle");
    };
    rec.current = r; r.start(); setSeconds(0); setState("recording");
    timer.current = window.setInterval(() => setSeconds((x) => {
      if (x + 1 >= 30) rec.current?.state === "recording" && rec.current.stop();  // keep questions short
      return x + 1;
    }), 1000);
  }
  const stop = () => { if (rec.current?.state === "recording") rec.current.stop(); };
  useEffect(() => () => { clearInterval(timer.current); if (rec.current?.state === "recording") rec.current.stop(); }, []);
  return { supported, state, seconds, start, stop };
}

function VoiceExplainer({ text, lang, audioUrl }: { text: string; lang: string; audioUrl?: string | null }) {
  const L = useL();
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
        <span className="block text-sm font-bold">{playing ? L.playing : L.listen}</span>
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

function Quote({ p }: { p: { quote?: string; page?: number | null } }) {
  const L = useL();
  if (!p.quote) return null;
  return (
    <details className="group mt-1">
      <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-xs font-semibold text-navy-500 hover:text-navy-800">
        <BookOpen className="size-3.5" />{L.from_document}{p.page ? `, ${L.page} ${p.page}` : ""}
      </summary>
      <blockquote className="mt-1 border-l-4 border-saffron-300 bg-saffron-50/60 px-3 py-1.5 text-sm italic text-slate-700">“{p.quote}”</blockquote>
    </details>
  );
}

function Points({ title, items, icon, empty }: { title: string; items: Point[]; icon: React.ReactNode; empty?: string }) {
  if (!items.length && !empty) return null;
  return (
    <Card variant="plain" className="p-5">
      <h3 className="flex items-center gap-2 text-lg font-extrabold text-navy-900">{icon}{title}</h3>
      {items.length ? (
        <ul className="mt-3 space-y-3">
          {items.map((p, i) => <li key={i} className="text-slate-800"><span className="leading-relaxed">{p.text}</span><Quote p={p} /></li>)}
        </ul>
      ) : <p className="mt-2 text-sm text-slate-500">{empty}</p>}
    </Card>
  );
}

function AnswerPanel({ ex, lang }: { ex: Explanation; lang: string }) {
  const L = { ...LABELS, ...(ex.labels ?? {}) };
  return (
    <LabelsCtx.Provider value={L}>
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="space-y-5" lang={lang.split("-")[0]} dir={lang === "ur-IN" ? "rtl" : undefined}>
      <Card variant="plain" className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-saffron-700">{[ex.doc.issuer, ex.doc.date].filter(Boolean).join(" · ") || "Official document"}</p>
            <h2 className="mt-1 text-2xl font-extrabold text-navy-900">{ex.title}</h2>
            {ex.doc.url && <a href={ex.doc.url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 break-all text-sm text-navy-600 underline-offset-2 hover:underline">{ex.doc.url.replace(/^https?:\/\//, "")}<ExternalLink className="size-3.5 shrink-0" /></a>}
          </div>
          <div className="flex flex-col items-end gap-1">
            <VoiceExplainer text={ex.voice_script || ex.answer} lang={lang} audioUrl={ex.audio_url} />
            <span className="text-[11px] text-slate-500">{ex.audio_url ? `Voice: ${ex.voice_provider}` : "Voice: your device's own speech"}</span>
          </div>
        </div>
        <div className="mt-5 rounded-2xl bg-navy-50 p-4">
          <p className="text-xs font-bold uppercase tracking-wider text-navy-600">{L.your_question}</p>
          <p className="text-sm text-slate-700">{ex.question}</p>
          {ex.language_from_question && (
            <p className="mt-1 inline-flex items-center gap-1 rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-navy-700 ring-1 ring-navy-100">
              <Languages className="size-3.5" />{LANGS.find((x) => x.code === ex.language)?.label}
            </p>
          )}
          <p className="mt-3 whitespace-pre-line text-lg leading-relaxed text-slate-900">{ex.answer}</p>
        </div>
        <p className="mt-4 leading-relaxed text-slate-700"><span className="font-bold text-navy-800">{L.in_short}: </span>{ex.summary}</p>
        {ex.doc.ocr && (
          <p className="mt-3 flex items-start gap-2 rounded-xl bg-saffron-50 px-3 py-2 text-sm text-saffron-800 ring-1 ring-saffron-200">
            <ScanText className="mt-0.5 size-4 shrink-0" />{ex.doc.ocr.reason === "indian_script" ? "This PDF's built-in text in an Indian script is often garbled, so" : "This was a scanned document, so"} the AI read {ex.doc.ocr.pages_read} of its {ex.doc.ocr.pages_total} page(s) from the page images. Quotes are checked against that reading: compare important figures with the original.
          </p>
        )}
        {ex.apply && (
          <Link to={`/agent?service=${ex.apply.portal_id}/${ex.apply.service_id}`} className="mt-4 inline-block">
            <Button variant="saffron"><Bot className="size-4" />{ex.apply.label ?? "Apply with the agent"}<ArrowRight className="size-4" /></Button>
          </Link>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Points title={L.rights} items={ex.rights} icon={<Scale className="size-5 text-saffron-600" />} empty={L.no_rights} />
        {ex.eligibility.length > 0 && (
          <Card variant="clay" className="p-5">
            <h3 className="flex items-center gap-2 text-lg font-extrabold text-navy-900"><UserCheck className="size-5 text-leaf-600" />{L.eligible}</h3>
            <ul className="mt-3 space-y-3">
              {ex.eligibility.map((e, i) => (
                <li key={i} className="flex items-start gap-2">
                  {e.met ? <CircleCheck className="mt-0.5 size-5 shrink-0 text-leaf-600" aria-label="You meet this" /> : e.met === false ? <CircleX className="mt-0.5 size-5 shrink-0 text-red-600" aria-label="You do not meet this" /> : <Info className="mt-0.5 size-5 shrink-0 text-slate-400" aria-label="Not known from your question" />}
                  <span className="min-w-0"><span className="font-semibold text-slate-900">{e.criterion}</span>{e.note && <span className="block text-sm text-slate-600">{e.note}</span>}<Quote p={e} /></span>
                </li>
              ))}
            </ul>
          </Card>
        )}
        <Points title={L.citizens} items={ex.impacts.citizens} icon={<Users className="size-5 text-navy-600" />} />
        <Points title={L.business} items={ex.impacts.business} icon={<Store className="size-5 text-navy-600" />} empty={L.no_business} />
        <Points title={L.deadlines} items={ex.deadlines} icon={<CalendarClock className="size-5 text-red-600" />} />
        {ex.how_to_act.length > 0 && (
          <Card variant="plain" className="p-5">
            <h3 className="flex items-center gap-2 text-lg font-extrabold text-navy-900"><ListChecks className="size-5 text-leaf-600" />{L.what_to_do}</h3>
            <ol className="mt-3 space-y-3">
              {ex.how_to_act.map((p, i) => (
                <li key={i} className="flex gap-3"><span className="grid size-7 shrink-0 place-items-center rounded-full bg-saffron-500 text-sm font-bold text-navy-900">{i + 1}</span><span className="min-w-0 text-slate-800">{p.text}<Quote p={p} /></span></li>
              ))}
            </ol>
          </Card>
        )}
      </div>
      <p className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
        <ShieldCheck className="size-4 text-leaf-600" />{L.checked}
        {ex.dropped_unverified > 0 && <span>{ex.dropped_unverified} point(s) were dropped because their quote was not in the document.</span>}
        {ex.untranslated > 0 && <span>{ex.untranslated} line(s) are shown in English because translation missed them.</span>}
        {ex.timing && <span className="font-mono text-xs text-slate-500">{(ex.timing.ms / 1000).toFixed(0)} s · {ex.timing.ai_calls} AI calls{ex.cached ? " · reused" : ""}</span>}
      </p>
    </motion.div>
    </LabelsCtx.Provider>
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
  // Until the citizen picks a language, the answer follows the language of their question.
  const [langPicked, setLangPicked] = useState(() => LANGS.some((item) => item.code === initialLanguage));
  const [mode, setMode] = useState<"link" | "pdf" | "text">("link");
  const [link, setLink] = useState(() => searchParams.get("url") ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [pasted, setPasted] = useState("");
  const [doc, setDoc] = useState<Doc | null>(null);
  const [docKey, setDocKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [stages, setStages] = useState<Stage[]>([]);
  const [ex, setEx] = useState<Explanation | null>(null);
  const [notConnected, setNotConnected] = useState(false);
  const voice = useVoiceQuestion(langPicked ? lang : null, (text, language) => {
    setQ((x) => (x ? `${x} ${text}` : text));
    if (!langPicked && language && LANGS.some((l) => l.code === language)) setLang(language);
  }, (m) => toast("error", m));
  const sourceKey = mode === "link" ? `link:${link.trim()}` : mode === "pdf" ? `pdf:${file?.name}:${file?.size}` : `text:${pasted.length}:${pasted.slice(0, 80)}`;

  useEffect(() => {
    api.config().then(setConfig).catch(() => {});
    api.services().then((s) => setFinder(s.find((x) => x.portal_id === "myscheme" && x.service_id === "find_schemes") ?? null)).catch(() => {});
  }, []);

  // While working, show the real pipeline stages with their timings.
  useEffect(() => {
    if (!busy) return;
    let stop = false, timer: number | undefined;
    const tick = () => api.part1("api/pipeline/latest").then((st) => !stop && setStages(st.nodes)).catch(() => {}).finally(() => { if (!stop) timer = window.setTimeout(tick, 900); });
    tick();
    return () => { stop = true; clearTimeout(timer); };
  }, [busy]);

  async function ingest(): Promise<Doc> {
    if (doc && docKey === sourceKey) return doc;
    const fd = new FormData();
    if (mode === "link") fd.append("url", link.trim());
    else if (mode === "pdf" && file) fd.append("file", file);
    else fd.append("text", pasted);
    const r = await fetch("/app/part1/api/documents", { method: "POST", body: fd });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof body.detail === "string" ? body.detail : `Could not read the document (${r.status})`);
    setDoc(body); setDocKey(sourceKey);
    return body;
  }

  async function explain(language = lang, picked = langPicked) {
    if (!config?.part1_connected) { setNotConnected(true); setEx(null); return; }
    const empty = mode === "link" ? !link.trim() : mode === "pdf" ? !file : pasted.trim().length < 200;
    if (empty) { toast("error", mode === "text" ? "Paste at least a paragraph of the notice." : "Add the notification: a link or a PDF."); return; }
    setBusy(true); setNotConnected(false); setStages([]);
    try {
      const d = await ingest();
      const res: Explanation = await api.part1("api/explain", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doc_id: d.doc_id, question: q, language, auto_language: !picked && q.trim().length > 0 }) });
      setEx(res);
      remember({
        kind: "explain", title: res.title.slice(0, 200), subtitle: `${LANGS.find((l) => l.code === res.language)?.label ?? res.language} · ${res.question}`.slice(0, 300),
        link: d.url ? `/schemes?url=${encodeURIComponent(d.url)}&lang=${res.language}` : "/schemes", meta: { doc_id: d.doc_id },
      });
      if (res.language !== language) setLang(res.language);
    } catch (err) { toast("error", (err as Error).message); }
    setBusy(false);
  }

  function ask(e: FormEvent) { e.preventDefault(); explain(); }
  const tab = (m: typeof mode, icon: React.ReactNode, label: string) => (
    <button type="button" role="tab" aria-selected={mode === m} onClick={() => setMode(m)}
      className={`inline-flex min-h-10 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold ${mode === m ? "bg-navy-700 text-white" : "text-navy-700 hover:bg-navy-50"}`}>{icon}{label}</button>
  );

  return (
    <div>
      <section className="mx-auto grid max-w-7xl items-start gap-10 px-4 pb-10 pt-10 lg:grid-cols-[1.25fr_1fr]">
        <motion.div initial="hidden" animate="show" variants={stagger}>
          <motion.div variants={fadeUp}><Badge tone="leaf">Part 1 · Rights & policy explainer</Badge></motion.div>
          <motion.h1 variants={fadeUp} className="mt-4 text-4xl font-extrabold leading-tight text-navy-900 sm:text-5xl">Know your rights, in your language.</motion.h1>
          <motion.p variants={fadeUp} className="mt-4 max-w-xl text-lg text-slate-700">Give us a government notification, policy draft, scheme page or municipal order. You get your rights, who is eligible and what changes for you or your shop, in plain words and in your language, with a voice explainer. Every point quotes the document.</motion.p>
          <motion.form variants={fadeUp} onSubmit={ask} className="glass mt-7 space-y-3 rounded-3xl p-4">
            <div>
              <p className="mb-2 text-sm font-bold text-navy-800">1. The document</p>
              <div className="flex flex-wrap gap-1" role="tablist" aria-label="How to add the document">
                {tab("link", <Link2 className="size-4" />, "Link")}{tab("pdf", <FileUp className="size-4" />, "PDF")}{tab("text", <ClipboardPaste className="size-4" />, "Paste text")}
              </div>
              <div className="mt-2">
                {mode === "link" && (
                  <>
                    <label htmlFor="doclink" className="sr-only">Link to the official document</label>
                    <input id="doclink" type="url" value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://…gov.in/…  (official .gov.in or .nic.in link)"
                      className="min-h-12 w-full rounded-xl border border-navy-100 bg-white/90 px-3.5 text-base text-slate-900 outline-none focus:ring-4 focus:ring-navy-100" />
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {SAMPLES.map((x) => <button type="button" key={x.url} onClick={() => setLink(x.url)} className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-navy-700 ring-1 ring-navy-100 hover:ring-navy-300">Try: {x.label}</button>)}
                    </div>
                  </>
                )}
                {mode === "pdf" && (
                  <label className="flex min-h-12 cursor-pointer items-center gap-2 rounded-xl border border-dashed border-navy-200 bg-white/90 px-3.5 text-sm text-slate-700 hover:border-navy-400">
                    <FileUp className="size-4 text-navy-500" />{file ? `${file.name} (${Math.round(file.size / 1024)} KB)` : "Choose a PDF (typed or scanned)"}
                    <input type="file" accept="application/pdf" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                  </label>
                )}
                {mode === "text" && (
                  <>
                    <label htmlFor="pasted" className="sr-only">Text of the notice</label>
                    <textarea id="pasted" rows={5} value={pasted} onChange={(e) => setPasted(e.target.value)} placeholder="Paste the full text of the notice here"
                      className="w-full rounded-xl border border-navy-100 bg-white/90 px-3.5 py-2.5 text-base text-slate-900 outline-none focus:ring-4 focus:ring-navy-100" />
                  </>
                )}
              </div>
            </div>
            <div>
              <label htmlFor="q" className="mb-2 block text-sm font-bold text-navy-800">2. Your question <span className="font-normal text-slate-500">(optional: tell us about you for an eligibility check)</span></label>
              <div className="flex items-center gap-2 rounded-xl border border-navy-100 bg-white/90 px-2">
                <Search className="ml-1 size-5 shrink-0 text-navy-400" aria-hidden />
                <input id="q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. मैं 52 साल का दुकानदार हूँ, क्या मुझे यह मिलेगा?"
                  className="min-h-12 min-w-0 flex-1 bg-transparent text-base text-slate-900 outline-none placeholder:text-slate-400" />
                {voice.supported && (
                  <button type="button" onClick={() => (voice.state === "recording" ? voice.stop() : voice.start())} disabled={voice.state === "transcribing"}
                    aria-label={voice.state === "recording" ? "Stop recording" : "Ask by voice"}
                    className={`inline-flex h-10 min-w-10 items-center justify-center gap-1 rounded-xl px-2 text-sm font-semibold ${voice.state === "recording" ? "pulse-ring bg-saffron-500 text-navy-900" : "bg-navy-50 text-navy-700 hover:bg-navy-100"} disabled:opacity-60`}>
                    {voice.state === "recording" ? <><Square className="size-4" />{voice.seconds}s</> : voice.state === "transcribing" ? <LoaderCircle className="size-4 animate-spin" /> : <Mic className="size-5" />}
                  </button>
                )}
              </div>
              {voice.state !== "idle" && (
                <p className="mt-1.5 text-xs font-semibold text-navy-600" role="status">
                  {voice.state === "recording" ? "Listening… tap ■ when you finish (30 s max)." : "Writing down what you said… please check it before asking."}
                </p>
              )}
            </div>
            <div>
              <p className="mb-2 text-sm font-bold text-navy-800">3. Your language <span className="font-normal text-slate-500">{langPicked ? "" : "(or just ask in your language: we answer in it)"}</span></p>
              <div className="flex flex-wrap gap-1.5">
                {LANGS.map((l) => (
                  <button type="button" key={l.code} onClick={() => { setLang(l.code); setLangPicked(true); if (ex && !busy) explain(l.code, true); }} aria-pressed={lang === l.code}
                    className={`rounded-full px-3 py-1 text-sm font-semibold ${lang === l.code ? "bg-navy-700 text-white" : "bg-white text-navy-700 ring-1 ring-navy-100 hover:ring-navy-300"}`}>{l.label}</button>
                ))}
              </div>
            </div>
            <Button type="submit" variant="saffron" loading={busy} className="w-full !rounded-2xl">Explain this document</Button>
          </motion.form>
          <Link to="/schemes/engine" className="mt-4 inline-flex items-center gap-1.5 text-sm font-bold text-navy-700 hover:text-saffron-700"><Workflow className="size-4" />See how answers are made (the engine room)</Link>
        </motion.div>
        <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.45 }} className="lg:sticky lg:top-28">
          <Card variant="clay" className="overflow-hidden bg-white p-2"><img src="/images/civic-schemes-guide-3d.webp" alt="A citizen checks her eligibility and support options on a phone" className="aspect-[4/3] w-full rounded-[1.35rem] object-cover" /></Card>
        </motion.div>
      </section>

      <section className="mx-auto max-w-7xl px-4">
        <AnimatePresence mode="wait">
          {busy && (
            <motion.div key="busy" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="relative overflow-hidden rounded-3xl bg-white p-6 ring-1 ring-navy-100">
              <div className="shimmer absolute inset-0" />
              <p className="relative flex items-center gap-2 font-semibold text-navy-800"><LoaderCircle className="size-5 animate-spin" />Reading the official document… this takes about a minute.</p>
              <ol className="relative mt-4 flex flex-wrap gap-2">
                {stages.filter((st) => st.id !== "embed").map((st) => (
                  <li key={st.id} className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${st.status === "done" ? "bg-leaf-100 text-leaf-700" : st.status === "running" ? "bg-saffron-100 text-saffron-700" : st.status === "error" ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-500"}`}>
                    {st.status === "done" ? <CircleCheck className="size-3.5" /> : st.status === "running" ? <LoaderCircle className="size-3.5 animate-spin" /> : null}
                    {STAGE_LABEL[st.id] ?? st.id}{st.ms != null && st.status === "done" && st.ms > 300 ? ` · ${(st.ms / 1000).toFixed(0)}s` : ""}
                  </li>
                ))}
              </ol>
            </motion.div>
          )}
          {ex && !busy && <AnswerPanel key={ex.language + ex.doc.doc_id} ex={ex} lang={lang} />}
          {notConnected && !busy && (
            <motion.div key="nc" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
              <NotConnected part="The explainer (Part 1)" endpoint="AIMLAPI_KEY" what="It needs an AI model to read the document. Meanwhile, the live scheme finder below already works." />
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
