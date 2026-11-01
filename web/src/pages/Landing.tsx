import { motion } from "motion/react";
import { ArrowRight, Bot, CheckCircle2, ClipboardCheck, FileCheck2, MapPinned, ShieldCheck, Sparkles, UsersRound } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Run } from "../api";
import { AgentArt, KnowArt, ReportArt } from "../components/Illustrations";
import { Badge, Card, CountUp, fadeUp, stagger } from "../components/ui";

function LiveSignal() {
  const [runs, setRuns] = useState<Run[]>([]);
  useEffect(() => { api.runs().then(setRuns).catch(() => setRuns([])); }, []);
  const values = useMemo(() => ({
    started: runs.length,
    completed: runs.filter((r) => r.status === "completed").length,
    filed: runs.filter((r) => Boolean(r.reference_no)).length,
  }), [runs]);
  return (
    <section className="mx-auto -mt-7 max-w-6xl px-4 sm:-mt-9" aria-label="Live platform activity">
      <div className="relative grid overflow-hidden rounded-3xl bg-white shadow-[0_18px_48px_-24px_rgb(19_48_107/0.34)] ring-1 ring-navy-100 sm:grid-cols-3">
        {[
          [values.started, "Tasks recorded by this server"],
          [values.completed, "Completed outcomes"],
          [values.filed, "Reference numbers captured"],
        ].map(([value, label], index) => (
          <div key={String(label)} className={`px-6 py-5 text-center ${index ? "border-t border-navy-100 sm:border-l sm:border-t-0" : ""}`}>
            <div className="font-display text-3xl font-extrabold text-navy-900"><CountUp value={Number(value)} /></div>
            <div className="mt-1 text-sm font-medium text-slate-600">{String(label)}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function Landing() {
  return <>
    <section className="relative isolate overflow-hidden border-b border-navy-100 bg-[#f8fafc]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_4%_18%,rgba(255,153,51,.16),transparent_32%),radial-gradient(circle_at_88%_92%,rgba(19,136,8,.10),transparent_30%)]" />
      <div className="relative mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:py-20 lg:grid-cols-[1.02fr_.98fr] lg:items-center lg:py-24">
        <motion.div initial="hidden" animate="show" variants={stagger} className="max-w-2xl">
          <motion.div variants={fadeUp}><Badge tone="saffron"><Sparkles className="size-3.5" />A civic-services companion</Badge></motion.div>
          <motion.h1 variants={fadeUp} className="mt-5 text-5xl font-extrabold text-navy-900 sm:text-6xl lg:text-7xl">Public services, made clearer.</motion.h1>
          <motion.p variants={fadeUp} className="mt-5 max-w-xl text-lg leading-8 text-slate-700 sm:text-xl">Swayam-sevak helps people discover support, report neighbourhood issues and complete official steps with a human in control.</motion.p>
          <motion.div variants={fadeUp} className="mt-8 flex flex-wrap gap-3">
            <Link to="/signin" className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-navy-700 px-5 font-semibold text-white shadow-[0_10px_24px_-11px_rgb(19_48_107/.72)] transition hover:-translate-y-0.5 hover:bg-navy-800">Get started <ArrowRight className="size-4" /></Link>
            <Link to="/board" className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-white px-5 font-semibold text-navy-800 ring-1 ring-navy-200 transition hover:-translate-y-0.5 hover:ring-navy-400">View service activity</Link>
          </motion.div>
          <motion.ul variants={fadeUp} className="mt-8 grid gap-3 text-sm font-medium text-navy-800 sm:grid-cols-3">
            {[
              [ShieldCheck, "You approve every final submission"],
              [CheckCircle2, "Source-backed answers"],
              [UsersRound, "Citizen and municipal workspaces"],
            ].map(([Icon, text]) => <li key={String(text)} className="flex items-start gap-2"><Icon className="mt-0.5 size-4 shrink-0 text-leaf-600" />{String(text)}</li>)}
          </motion.ul>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5, delay: .15 }} className="relative mx-auto w-full max-w-2xl">
          <div className="absolute -inset-4 -z-10 rounded-[2.4rem] bg-gradient-to-br from-saffron-200/50 via-transparent to-leaf-100/70 blur-2xl" />
          <img src="/images/civic-landing-community.webp" alt="Indian citizens using a phone together outside a community service centre" fetchPriority="high" decoding="async" className="aspect-[16/10] w-full rounded-[2rem] object-cover shadow-[0_24px_55px_-25px_rgb(19_48_107/.5)] ring-1 ring-white/80" />
          <div className="absolute bottom-4 left-4 max-w-56 rounded-2xl bg-white/95 p-3 shadow-lg backdrop-blur sm:bottom-6 sm:left-6 sm:p-4">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[.14em] text-leaf-700"><span className="size-2 rounded-full bg-leaf-500" />Guided, not automated away</div>
            <p className="mt-1.5 text-sm font-medium leading-5 text-navy-900">The person decides. The system makes the path simpler.</p>
          </div>
        </motion.div>
      </div>
    </section>

    <LiveSignal />

    <section className="mx-auto max-w-7xl px-4 py-16 sm:py-20" aria-labelledby="people-title">
      <div className="grid gap-7 lg:grid-cols-[.9fr_1.1fr] lg:items-end"><div><Badge tone="leaf">The work is human</Badge><h2 id="people-title" className="mt-4 text-4xl font-extrabold text-navy-900">Built around the people who report, respond and repair.</h2><p className="mt-3 max-w-xl text-lg leading-8 text-slate-600">A good civic system keeps the citizen visible, gives field teams a clearer brief and lets service desks show what actually changed.</p></div><figure className="overflow-hidden rounded-3xl bg-white shadow-[0_16px_35px_-24px_rgb(19_48_107/.42)] ring-1 ring-navy-100"><img src="/images/civic-reporting-repair.webp" loading="lazy" decoding="async" alt="Resident documenting a street repair while a field crew works nearby" className="aspect-[16/9] w-full object-cover" /><figcaption className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm"><span className="font-semibold text-navy-900">Report → verify → repair</span><span className="text-slate-500">Illustrative Swayam-sevak workflow</span></figcaption></figure></div>
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[{ src: "/images/commons-pondicherry-sanitation.webp", alt: "Sanitation workers in Pondicherry", label: "The people who keep a city moving", credit: "Muhammed Shafi / CC BY 2.0", href: "https://commons.wikimedia.org/wiki/File:Sanitation_workers_of_Pondicherry.jpg" }, { src: "/images/commons-kolkata-street.webp", alt: "Street life in Kolkata", label: "Everyday context matters", credit: "Vyacheslav Argenberg / CC BY 4.0", href: "https://commons.wikimedia.org/wiki/File:Life_on_the_streets_of_Kolkata_2,_India.jpg" }, { src: "/images/commons-kolkata-worker.webp", alt: "Worker in Kolkata", label: "Field work deserves clear information", credit: "Indrajit Das / CC BY 4.0", href: "https://commons.wikimedia.org/wiki/File:Daily_wage_labour_in_Kolkata_04.jpg" }, { src: "/images/commons-mcd-hq.webp", alt: "Municipal Corporation of Delhi civic centre", label: "A more accountable desk", credit: "Nikhil B / Wikimedia Commons", href: "https://commons.wikimedia.org/wiki/File:MCD_HQ.jpg" }].map((photo) => <figure key={photo.src} className="group overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-navy-100"><img src={photo.src} loading="lazy" decoding="async" alt={photo.alt} className="aspect-[4/3] w-full object-cover transition duration-300 group-hover:scale-[1.03]" /><figcaption className="p-3"><div className="text-sm font-bold leading-5 text-navy-900">{photo.label}</div><a href={photo.href} target="_blank" rel="noreferrer" className="mt-1 block text-xs text-slate-500 underline-offset-2 hover:text-navy-700 hover:underline">{photo.credit}</a></figcaption></figure>)}
      </div>
    </section>

    <section className="mx-auto max-w-7xl px-4 py-20" aria-labelledby="journey-title">
      <div className="mx-auto max-w-2xl text-center"><Badge tone="navy">One connected civic journey</Badge><h2 id="journey-title" className="mt-4 text-4xl font-extrabold text-navy-900">From a question to a traceable outcome.</h2><p className="mt-3 text-lg text-slate-600">Each part has a different job. Together, they give citizens and the service desk a shared, honest record.</p></div>
      <div className="mt-10 grid gap-5 lg:grid-cols-3">
        {[
          { icon: KnowArt, num: "01", title: "Understand what is available", body: "Search official scheme information in plain language and review the source before you continue.", link: "/schemes", label: "Find schemes" },
          { icon: ReportArt, num: "02", title: "Make a civic issue visible", body: "Report a problem with evidence and location. The public board shows its real status, not a made-up promise.", link: "/grievance", label: "Report an issue" },
          { icon: AgentArt, num: "03", title: "Complete the official steps", body: "The agent works in a controlled browser, stops for OTPs and asks for approval before any submission.", link: "/agent", label: "Open the agent" },
        ].map((item) => <Card key={item.num} variant="plain" className="group relative overflow-hidden p-6 transition duration-200 hover:-translate-y-1 hover:shadow-lg"><span className="absolute right-6 top-5 font-display text-5xl font-extrabold text-navy-100">{item.num}</span><item.icon className="relative h-36 w-full" title={item.title} /><h3 className="mt-4 text-2xl font-extrabold text-navy-900">{item.title}</h3><p className="mt-2 min-h-14 text-sm leading-6 text-slate-600">{item.body}</p><Link to={item.link} className="mt-5 inline-flex items-center gap-1.5 text-sm font-bold text-navy-700 hover:text-saffron-700">{item.label}<ArrowRight className="size-4 transition group-hover:translate-x-1" /></Link></Card>)}
      </div>
    </section>

    <section className="border-y border-navy-100 bg-white/70" aria-labelledby="roles-title">
      <div className="mx-auto max-w-7xl px-4 py-20"><div className="max-w-2xl"><Badge tone="leaf">A clear desk for each role</Badge><h2 id="roles-title" className="mt-4 text-4xl font-extrabold text-navy-900">Different workspaces. One public record.</h2></div>
        <div className="mt-9 grid gap-5 lg:grid-cols-2">
          <article className="relative overflow-hidden rounded-3xl bg-navy-800 p-7 text-white sm:p-9"><div className="absolute -right-8 -top-8 size-36 rounded-full border-[18px] border-saffron-400/25" /><MapPinned className="size-7 text-saffron-400" /><h3 className="mt-5 text-3xl font-extrabold">For citizens</h3><p className="mt-3 max-w-md text-navy-100">Start an application, report a local problem, follow clear next steps and keep the receipt you can verify.</p><Link to="/signin?role=citizen" className="mt-7 inline-flex min-h-11 items-center gap-2 rounded-xl bg-white px-4 font-bold text-navy-800 transition hover:bg-navy-50">Continue as citizen <ArrowRight className="size-4" /></Link></article>
          <article className="relative overflow-hidden rounded-3xl bg-leaf-50 p-7 ring-1 ring-leaf-200 sm:p-9"><div className="absolute -right-8 -top-8 size-36 rounded-full border-[18px] border-leaf-200" /><ClipboardCheck className="size-7 text-leaf-700" /><h3 className="mt-5 text-3xl font-extrabold text-navy-900">For municipal desks</h3><p className="mt-3 max-w-md text-slate-700">Review the triage queue, correct AI suggestions, assign work and close a case only with photo evidence.</p><Link to="/signin?role=admin" className="mt-7 inline-flex min-h-11 items-center gap-2 rounded-xl bg-leaf-600 px-4 font-bold text-white transition hover:bg-leaf-700">Municipal sign in <ArrowRight className="size-4" /></Link></article>
        </div>
      </div>
    </section>

    <section className="mx-auto max-w-7xl px-4 py-16 sm:py-20" aria-labelledby="field-title"><div className="grid gap-7 overflow-hidden rounded-[2rem] bg-navy-800 p-7 text-white sm:p-10 lg:grid-cols-[1fr_.92fr] lg:items-center"><div><Badge tone="saffron">For the people on the ground</Badge><h2 id="field-title" className="mt-4 text-4xl font-extrabold">A clearer handoff from desk to field team.</h2><p className="mt-4 max-w-xl text-lg leading-8 text-navy-100">Municipal operators can turn a triaged issue into a readable field brief: evidence, location, severity and the work that still needs a human decision.</p><Link to="/signin?role=admin" className="mt-7 inline-flex min-h-11 items-center gap-2 rounded-xl bg-white px-4 font-bold text-navy-800 transition hover:bg-navy-50">See the municipal desk <ArrowRight className="size-4" /></Link></div><figure className="overflow-hidden rounded-2xl bg-white/10 ring-1 ring-white/15"><img src="/images/civic-field-team.webp" loading="lazy" decoding="async" alt="Illustrative municipal field team reviewing a location map together" className="aspect-[4/3] w-full object-cover" /><figcaption className="px-4 py-3 text-xs text-navy-100">Illustrative Swayam-sevak workflow</figcaption></figure></div></section>

    <section className="mx-auto max-w-7xl px-4 py-20"><div className="grid gap-8 rounded-[2rem] bg-[#fff7ed] p-7 ring-1 ring-saffron-100 sm:p-10 lg:grid-cols-[1.25fr_.75fr] lg:items-center"><div><Badge tone="saffron">Trust is a product feature</Badge><h2 className="mt-4 text-4xl font-extrabold text-navy-900">Designed to show its work.</h2><p className="mt-3 max-w-2xl text-lg leading-8 text-slate-700">Swayam-sevak is a hackathon prototype, not an official government site. It labels live sources, pauses for human-only steps and records what happened so a claim can be checked.</p><Link to="/board" className="mt-7 inline-flex items-center gap-2 font-bold text-navy-800 hover:text-saffron-700">See the accountability board <ArrowRight className="size-4" /></Link></div><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">{[[ShieldCheck, "Consent before submission"], [FileCheck2, "Receipts you can verify"]].map(([Icon, label]) => <div key={String(label)} className="flex items-center gap-3 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-saffron-100"><Icon className="size-5 text-saffron-700" /><span className="font-bold text-navy-900">{String(label)}</span></div>)}</div></div></section>
  </>;
}
