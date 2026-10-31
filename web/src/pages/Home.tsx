import { motion, useReducedMotion } from "motion/react";
import { ArrowRight, BadgeCheck, Bot, FileCheck2, Hand, KeyRound, Megaphone, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, secs, type Run } from "../api";
import { AgentArt, HeroScene, KnowArt, ReportArt, StepArt } from "../components/Illustrations";
import { Button, Card, CountUp, fadeUp, SectionTitle, stagger } from "../components/ui";
import { useI18n } from "../i18n";

function Floating({ children, className, delay = 0 }: { children: React.ReactNode; className: string; delay?: number }) {
  const reduce = useReducedMotion();
  return (
    <motion.div className={`glass absolute flex items-center gap-2 rounded-2xl px-3 py-2 text-sm font-semibold text-navy-900 ${className}`}
      initial={{ opacity: 0, scale: 0.9 }} animate={reduce ? { opacity: 1, scale: 1 } : { opacity: 1, scale: 1, y: [0, -6, 0] }}
      transition={{ opacity: { delay, duration: 0.4 }, scale: { delay, duration: 0.4 }, y: { delay, duration: 4, repeat: Infinity, ease: "easeInOut" } }}>
      {children}
    </motion.div>
  );
}

function WhatsNew({ runs }: { runs: Run[] }) {
  const reduce = useReducedMotion();
  const items = runs.filter((r) => r.status === "completed").slice(0, 8).map((r) =>
    r.service_id === "find_schemes" ? `Live myScheme lookup finished · ${r.results ?? 0} schemes · ${secs(r.timing.agent_ms)}`
      : r.reference_no ? `Grievance filed in the sandbox · ${r.reference_no}` : `${r.service} · ${r.outcome?.replace(/_/g, " ")}`);
  if (!items.length) return null;
  return (
    <div className="border-y border-saffron-200 bg-saffron-50/90">
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-2 text-sm">
        <span className="flex shrink-0 items-center gap-1.5 rounded-md bg-saffron-500 px-2 py-0.5 text-xs font-bold text-navy-900"><Megaphone className="size-3.5" />What's new</span>
        <div className="relative flex-1 overflow-hidden" aria-live="off">
          <motion.div className="flex w-max gap-10 whitespace-nowrap text-navy-800" animate={reduce ? {} : { x: ["0%", "-50%"] }} transition={{ duration: 40, repeat: Infinity, ease: "linear" }}>
            {[...items, ...items].map((t, i) => <span key={i}>• {t}</span>)}
          </motion.div>
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  const { t } = useI18n();
  const [runs, setRuns] = useState<Run[]>([]);
  useEffect(() => { api.runs().then(setRuns).catch(() => {}); }, []);
  const stats = useMemo(() => {
    const done = runs.filter((r) => r.status === "completed");
    const lookups = done.filter((r) => r.service_id === "find_schemes");
    const times = lookups.map((r) => r.timing.agent_ms ?? 0).sort((a, b) => a - b);
    return {
      total: runs.length, completed: done.length,
      filings: done.filter((r) => r.reference_no).length,
      median: times.length ? times[Math.floor(times.length / 2)] / 1000 : 0,
    };
  }, [runs]);

  const pillars = [
    { art: KnowArt, title: t("navSchemes"), part: "Part 1", body: "Ask in your language. See which schemes you can get, with the official source, and listen to the answer.", to: "/schemes", cta: t("ctaSchemes"), tint: "from-leaf-50" },
    { art: ReportArt, title: t("navGrievance"), part: "Part 2", body: "Photograph a pothole or a leak. We locate it, sort it, and track it in public until it is fixed.", to: "/grievance", cta: t("ctaReport"), tint: "from-saffron-50" },
    { art: AgentArt, title: "Get it done", part: "Part 3", body: "Our agent fills the government portal in a real browser. You type the OTP and approve. You get a signed receipt.", to: "/agent", cta: "Watch the agent", tint: "from-navy-50" },
  ];
  const steps = [
    { n: 1 as const, title: "Tell us", body: "Answer a few questions, in English or Hindi." },
    { n: 2 as const, title: "The agent fills it", body: "Live, on the portal, step by step in plain words." },
    { n: 3 as const, title: "You approve", body: "You type the OTP and CAPTCHA and give the final yes." },
    { n: 4 as const, title: "You get a receipt", body: "A signed record with the portal's reference number." },
  ];

  return (
    <>
      <section className="relative overflow-hidden">
        <div className="mx-auto grid max-w-7xl items-center gap-10 px-4 pb-14 pt-10 lg:grid-cols-2 lg:pt-16">
          <motion.div initial="hidden" animate="show" variants={stagger}>
            <motion.p variants={fadeUp} className="mb-4 inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1 text-sm font-bold text-saffron-700 ring-1 ring-saffron-200">
              <span className="size-2 rounded-full bg-leaf-500" />{t("heroKicker")}
            </motion.p>
            <motion.h1 variants={fadeUp} className="text-4xl font-extrabold leading-[1.08] text-navy-900 sm:text-5xl lg:text-6xl">{t("heroTitle")}</motion.h1>
            <motion.p variants={fadeUp} className="mt-5 max-w-xl text-lg leading-relaxed text-slate-700">{t("heroBody")}</motion.p>
            <motion.div variants={fadeUp} className="mt-8 flex flex-wrap gap-3">
              <Link to="/schemes"><Button variant="saffron" className="text-base">{t("ctaSchemes")}<ArrowRight className="size-4" /></Button></Link>
              <Link to="/grievance"><Button variant="primary" className="text-base">{t("ctaReport")}</Button></Link>
              <Link to="/agent"><Button variant="ghost" className="text-base"><Bot className="size-4" />{t("watchAgent")}</Button></Link>
            </motion.div>
            <motion.ul variants={fadeUp} className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm font-medium text-slate-700">
              {[t("bulletLive"), t("bulletOtp"), t("bulletYes")].map((x) => (
                <li key={x} className="flex items-center gap-1.5"><BadgeCheck className="size-4 text-leaf-600" />{x}</li>
              ))}
            </motion.ul>
          </motion.div>
          <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }} className="relative">
            <Card variant="glass" className="p-4 sm:p-6"><HeroScene className="h-auto w-full" title="A citizen approves on her phone while the agent fills a portal form" /></Card>
            <Floating className="-left-2 top-6 sm:-left-6" delay={0.4}><KeyRound className="size-4 text-saffron-600" />OTP typed by you</Floating>
            <Floating className="-right-2 top-[62%] sm:-right-6" delay={0.7}><ShieldCheck className="size-4 text-leaf-600" />AI never sees your bank details</Floating>
            <Floating className="bottom-6 left-8" delay={1}><FileCheck2 className="size-4 text-navy-600" />Signed receipt</Floating>
          </motion.div>
        </div>
      </section>

      <WhatsNew runs={runs} />

      <section className="mx-auto max-w-7xl px-4 py-16">
        <SectionTitle kicker="Civic Pulse" title={t("pillarsTitle")}>One place to understand your rights, raise a problem, and get the paperwork done, with a person in control at every step.</SectionTitle>
        <motion.div initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.2 }} variants={stagger} className="grid gap-6 md:grid-cols-3">
          {pillars.map((p) => (
            <motion.div key={p.title} variants={fadeUp} whileHover={{ y: -6 }} className={`clay flex flex-col bg-gradient-to-b ${p.tint} to-white p-6`}>
              <p.art className="h-32 w-auto self-start" />
              <span className="mt-4 w-fit rounded-full bg-white px-2.5 py-0.5 text-xs font-bold text-navy-600 ring-1 ring-navy-100">{p.part}</span>
              <h3 className="mt-2 text-2xl font-extrabold text-navy-900">{p.title}</h3>
              <p className="mt-2 flex-1 text-slate-600">{p.body}</p>
              <Link to={p.to} className="mt-5 inline-flex items-center gap-1.5 font-bold text-navy-700 hover:gap-2.5 hover:text-saffron-700">{p.cta}<ArrowRight className="size-4" /></Link>
            </motion.div>
          ))}
        </motion.div>
      </section>

      <section className="bg-white/60 py-16">
        <div className="mx-auto max-w-7xl px-4">
          <SectionTitle kicker="Simple, step by step" title={t("howTitle")} />
          <motion.ol initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.2 }} variants={stagger} className="relative grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <div className="tricolor-bar absolute left-[12%] right-[12%] top-14 hidden h-1 rounded-full opacity-60 lg:block" aria-hidden />
            {steps.map((s) => (
              <motion.li key={s.n} variants={fadeUp} className="relative flex flex-col items-center text-center">
                <div className="clay grid size-28 place-items-center bg-white"><StepArt step={s.n} className="h-20 w-auto" /></div>
                <span className="mt-4 grid size-8 place-items-center rounded-full bg-navy-700 text-sm font-bold text-white">{s.n}</span>
                <h3 className="mt-2 text-lg font-bold text-navy-900">{s.title}</h3>
                <p className="mt-1 max-w-[16rem] text-slate-600">{s.body}</p>
              </motion.li>
            ))}
          </motion.ol>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-16">
        <SectionTitle kicker="Not a mock-up" title={t("liveTitle")}>Counted from real runs on this server: live lookups on myScheme.gov.in and filings in the sandbox replica.</SectionTitle>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { v: stats.total, label: "Tasks started", dec: 0, suf: "" },
            { v: stats.completed, label: "Completed", dec: 0, suf: "" },
            { v: stats.filings, label: "Filed with approval", dec: 0, suf: "" },
            { v: stats.median, label: "Median myScheme lookup", dec: 1, suf: "s" },
          ].map((s) => (
            <Card key={s.label} variant="glass" className="p-6">
              <div className="font-display text-4xl font-extrabold text-navy-900"><CountUp value={s.v} decimals={s.dec} suffix={s.suf} /></div>
              <div className="mt-1 text-sm font-medium text-slate-600">{s.label}</div>
            </Card>
          ))}
        </div>
        <Link to="/agent" className="mt-6 inline-flex items-center gap-1.5 font-bold text-navy-700 hover:text-saffron-700">Open the agent room<ArrowRight className="size-4" /></Link>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-6">
        <div className="clay overflow-hidden bg-navy-800 p-8 text-white sm:p-10">
          <h2 className="text-3xl font-extrabold">{t("trustTitle")}</h2>
          <div className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { icon: ShieldCheck, t: "Your consent first", b: "Every task starts with your explicit consent, limited to one portal and 24 hours." },
              { icon: KeyRound, t: "Private stays private", b: "Bank, phone and email are encrypted. The AI only ever sees placeholders." },
              { icon: Hand, t: "You hold the keys", b: "You type OTPs and CAPTCHAs yourself. Nothing is filed without your yes." },
              { icon: FileCheck2, t: "Proof you can check", b: "Receipts are signed, so anyone can verify they were not changed later." },
            ].map((x) => (
              <div key={x.t} className="rounded-2xl bg-white/5 p-5 ring-1 ring-white/10">
                <x.icon className="size-6 text-saffron-400" aria-hidden />
                <h3 className="mt-3 font-bold">{x.t}</h3>
                <p className="mt-1 text-sm text-navy-100">{x.b}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
