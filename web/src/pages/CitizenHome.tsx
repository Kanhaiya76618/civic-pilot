import { motion } from "motion/react";
import { ArrowRight, Bot, FileSearch, MapPinned, ReceiptText, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { api, type Run } from "../api";
import { getAuthSession } from "../auth";
import { Badge, Card, CountUp } from "../components/ui";

export default function CitizenHome() {
  const session = getAuthSession();
  const [runs, setRuns] = useState<Run[]>([]);
  useEffect(() => { if (session) api.runs().then(setRuns).catch(() => setRuns([])); }, [session]);
  const stats = useMemo(() => ({
    recorded: runs.length,
    complete: runs.filter((r) => r.status === "completed").length,
    receipts: runs.filter((r) => r.reference_no).length,
  }), [runs]);
  if (!session || session.user.role !== "citizen") return <Navigate to="/signin?role=citizen" replace />;
  const firstName = session.user.name.split(" ")[0] || "there";
  return <div className="mx-auto max-w-7xl px-4 py-10 sm:py-14">
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="relative overflow-hidden rounded-[2rem] bg-navy-800 px-6 py-10 text-white shadow-[0_24px_55px_-28px_rgb(19_48_107/.65)] sm:px-10 sm:py-12">
      <div className="absolute right-0 top-0 size-64 translate-x-1/3 -translate-y-1/3 rounded-full border-[36px] border-saffron-400/20" /><div className="absolute bottom-0 right-28 size-36 translate-y-1/2 rounded-full border-[24px] border-leaf-500/25" />
      <Badge tone="saffron"><Sparkles className="size-3.5" />Citizen workspace</Badge><h1 className="relative mt-4 text-4xl font-extrabold sm:text-5xl">Hello, {firstName}. What can we help with?</h1><p className="relative mt-3 max-w-2xl text-lg text-navy-100">Choose a service, keep control of your personal information, and follow the outcome from one place.</p>
    </motion.div>

    <section className="mt-8 grid gap-4 md:grid-cols-3" aria-label="Start a task">
      {[{ icon: FileSearch, title: "Find schemes", body: "Explore official scheme information and eligibility questions.", to: "/schemes", c: "bg-saffron-50 text-saffron-700" }, { icon: MapPinned, title: "Report a local problem", body: "Send evidence and a location to the civic triage flow.", to: "/grievance", c: "bg-leaf-50 text-leaf-700" }, { icon: Bot, title: "Ask the agent", body: "Research an allowed portal or work through a guided filing.", to: "/agent", c: "bg-navy-50 text-navy-700" }].map((item) => <Link key={item.title} to={item.to} className="group"><Card variant="plain" className="h-full p-6 transition duration-200 hover:-translate-y-1 hover:shadow-lg"><span className={`grid size-12 place-items-center rounded-2xl ${item.c}`}><item.icon className="size-6" /></span><h2 className="mt-5 text-xl font-extrabold text-navy-900">{item.title}</h2><p className="mt-2 text-sm leading-6 text-slate-600">{item.body}</p><span className="mt-5 inline-flex items-center gap-1 text-sm font-bold text-navy-700">Start <ArrowRight className="size-4 transition group-hover:translate-x-1" /></span></Card></Link>)}
    </section>

    <section className="mt-10 grid gap-6 lg:grid-cols-[1.25fr_.75fr]">
      <div><div className="flex items-end justify-between gap-4"><div><Badge tone="navy">Live server activity</Badge><h2 className="mt-3 text-3xl font-extrabold text-navy-900">A transparent path forward.</h2></div><Link to="/board" className="mb-1 hidden items-center gap-1 text-sm font-bold text-navy-700 hover:text-saffron-700 sm:inline-flex">Public board <ArrowRight className="size-4" /></Link></div>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">{[[stats.recorded, "Tasks recorded"], [stats.complete, "Completed outcomes"], [stats.receipts, "Reference numbers"]].map(([value, label]) => <Card key={String(label)} variant="glass" className="p-5"><div className="font-display text-4xl font-extrabold text-navy-900"><CountUp value={Number(value)} /></div><div className="mt-1 text-sm font-medium text-slate-600">{String(label)}</div></Card>)}</div>
        <Link to="/board" className="mt-5 inline-flex items-center gap-1 text-sm font-bold text-navy-700 hover:text-saffron-700 sm:hidden">Public board <ArrowRight className="size-4" /></Link>
      </div>
      <Card variant="dark" className="p-6"><div className="flex items-center gap-2 text-saffron-300"><ShieldCheck className="size-5" /><span className="text-sm font-bold uppercase tracking-wider">You stay in control</span></div><h2 className="mt-4 text-2xl font-extrabold text-white">The agent pauses for human-only actions.</h2><p className="mt-3 text-sm leading-6 text-navy-100">It never types your OTP, solves a CAPTCHA or completes a submission without your visible approval.</p><Link to="/agent" className="mt-6 inline-flex items-center gap-2 text-sm font-bold text-saffron-300 hover:text-saffron-200">See how it works <ArrowRight className="size-4" /></Link></Card>
    </section>

    <section className="mt-10 rounded-3xl border border-navy-100 bg-white/80 p-6 sm:p-8"><div className="flex flex-wrap items-start justify-between gap-4"><div><h2 className="text-2xl font-extrabold text-navy-900">Keep your record close.</h2><p className="mt-2 max-w-2xl text-slate-600">Use the public accountability board to see reported civic issues and verify visible service progress. Personal form data remains private.</p></div><ReceiptText className="size-8 text-saffron-600" /></div><Link to="/board" className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-xl bg-navy-700 px-4 font-semibold text-white transition hover:bg-navy-800">Open accountability board <ArrowRight className="size-4" /></Link></section>
  </div>;
}
