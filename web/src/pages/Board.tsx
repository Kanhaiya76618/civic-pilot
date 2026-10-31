import { motion } from "motion/react";
import { Bot, ChartColumn, CircleCheck, Clock, Inbox, MapPin, Radio, ShieldAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { api, secs, type AppConfig, type Run } from "../api";
import { Badge, Card, CountUp, fadeUp, NotConnected, stagger } from "../components/ui";

/** Part 2 contract (docs/UI_CONTRACT.md): GET /api/public/reports and GET /api/public/stats. */
type Report = { code: string; lat: number; lng: number; severity: "P1" | "P2" | "P3"; status: string; category: string; source: "citizen" | "agent"; ward?: string; sla_breached?: boolean };
type Stats = { total: number; open: number; resolved_pct: number; avg_resolution_hours: number; sla_breached: number };

const SEV_COLOR = { P1: "#DC2626", P2: "#FF9933", P3: "#138808" } as const;
const COLUMNS = [
  { id: "submitted", label: "Submitted", match: ["submitted", "acknowledged"] },
  { id: "routed", label: "Routed", match: ["assigned"] },
  { id: "review", label: "In progress", match: ["in_progress"] },
  { id: "resolved", label: "Resolved", match: ["resolved"] },
];

export default function Board() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [reports, setReports] = useState<Report[] | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => { api.config().then(setConfig).catch(() => {}); }, []);
  useEffect(() => {
    let stop = false, timer: number | undefined;
    const tick = async () => {
      try {
        setRuns(await api.runs());
        if (config?.part2_connected) {
          const [r, s] = await Promise.all([api.part2("api/public/reports"), api.part2("api/public/stats")]);
          if (!stop) { setReports(r); setStats(s); }
        }
      } catch { /* keep the last good data */ }
      if (!stop) timer = window.setTimeout(tick, 5000);
    };
    tick();
    return () => { stop = true; clearTimeout(timer); };
  }, [config?.part2_connected]);

  const filings = runs.filter((r) => r.service_id === "public_grievance" && r.reference_no);
  const agentStats = useMemo(() => {
    const times = filings.map((r) => r.timing.agent_ms ?? 0).sort((a, b) => a - b);
    return {
      filed: filings.length,
      districts: new Set(filings.map((r) => r.district).filter(Boolean)).size,
      median: times.length ? times[Math.floor(times.length / 2)] / 1000 : 0,
      lookups: runs.filter((r) => r.service_id === "find_schemes" && r.status === "completed").length,
    };
  }, [runs]); // eslint-disable-line react-hooks/exhaustive-deps
  const byCategory = useMemo(() => {
    const counts: Record<string, number> = {};
    [...filings.map((r) => r.category ?? "Other"), ...(reports ?? []).map((r) => r.category)].forEach((c) => (counts[c] = (counts[c] ?? 0) + 1));
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [filings, reports]);
  const maxCat = Math.max(1, ...byCategory.map(([, n]) => n));
  const pins = [
    ...(reports ?? []).map((r) => ({ key: r.code, at: [r.lat, r.lng] as [number, number], color: SEV_COLOR[r.severity] ?? "#2747A0", label: `${r.code} · ${r.category} · ${r.status}`, agent: r.source === "agent" })),
    ...filings.filter((r) => r.location).map((r) => ({ key: r.reference_no!, at: r.location!, color: "#2747A0", label: `${r.reference_no} · ${r.category} · filed by agent`, agent: true })),
  ];

  const cards = stats
    ? [
        { icon: Inbox, v: stats.total, label: "Reports", dec: 0, suf: "" },
        { icon: CircleCheck, v: stats.resolved_pct, label: "Resolved", dec: 0, suf: "%" },
        { icon: Clock, v: stats.avg_resolution_hours, label: "Avg. hours to resolve", dec: 0, suf: "h" },
        { icon: ShieldAlert, v: stats.sla_breached, label: "Past their deadline", dec: 0, suf: "" },
      ]
    : [
        { icon: Bot, v: agentStats.filed, label: "Grievances filed by the agent", dec: 0, suf: "" },
        { icon: MapPin, v: agentStats.districts, label: "Districts", dec: 0, suf: "" },
        { icon: Clock, v: agentStats.median, label: "Median agent time per filing", dec: 1, suf: "s" },
        { icon: ChartColumn, v: agentStats.lookups, label: "Live scheme lookups", dec: 0, suf: "" },
      ];

  return (
    <div className="mx-auto max-w-7xl px-4 py-10">
      <motion.div initial="hidden" animate="show" variants={stagger} className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <motion.div variants={fadeUp}><Badge tone="saffron">Part 2 · Public accountability</Badge></motion.div>
          <motion.h1 variants={fadeUp} className="mt-3 text-4xl font-extrabold text-navy-900 sm:text-5xl">Accountability board</motion.h1>
          <motion.p variants={fadeUp} className="mt-3 max-w-2xl text-lg text-slate-700">Every reported problem, where it is, and who is working on it. Open to everyone, no login.</motion.p>
        </div>
        <span className="flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-sm font-semibold text-navy-700 ring-1 ring-navy-100"><span className="size-2 animate-pulse rounded-full bg-leaf-500" />Live · updates every 5 s</span>
      </motion.div>

      {!stats && <p className="mt-4 rounded-2xl bg-navy-50 p-3 text-sm text-navy-800">Showing the agent's real filings from this server. When the triage service (Part 2) is connected, citizen reports, statuses and deadlines appear here too.</p>}

      <motion.div initial="hidden" animate="show" variants={stagger} className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((c) => (
          <motion.div key={c.label} variants={fadeUp}><Card variant="glass" className="p-5">
            <c.icon className="size-6 text-saffron-600" aria-hidden />
            <div className="mt-3 font-display text-4xl font-extrabold text-navy-900"><CountUp value={c.v} decimals={c.dec} suffix={c.suf} /></div>
            <div className="text-sm font-medium text-slate-600">{c.label}</div>
          </Card></motion.div>
        ))}
      </motion.div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <Card variant="plain" className="overflow-hidden p-2">
          <MapContainer center={[22.6, 79.5]} zoom={5} scrollWheelZoom={false} className="h-[26rem] w-full">
            <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            {pins.map((p) => (
              <CircleMarker key={p.key} center={p.at} radius={p.agent ? 9 : 8} pathOptions={{ color: p.agent ? "#13306B" : p.color, weight: p.agent ? 3 : 1, fillColor: p.color, fillOpacity: 0.75 }}>
                <Tooltip>{p.label}</Tooltip>
              </CircleMarker>
            ))}
          </MapContainer>
          <div className="flex flex-wrap gap-4 px-3 py-2 text-xs text-slate-600">
            {[["Critical", SEV_COLOR.P1], ["High", SEV_COLOR.P2], ["Medium", SEV_COLOR.P3], ["Filed by agent", "#2747A0"]].map(([l, c]) => <span key={l} className="flex items-center gap-1.5"><span className="size-3 rounded-full" style={{ background: c }} />{l}</span>)}
            {pins.length === 0 && <span>No located reports yet. Filings that share a location appear here, rounded to about 1 km.</span>}
          </div>
        </Card>

        <Card variant="plain" className="flex flex-col p-5">
          <h2 className="flex items-center gap-2 text-lg font-extrabold text-navy-900"><Radio className="size-5 text-saffron-600" />Agent follow-ups</h2>
          <ol className="mt-3 flex-1 space-y-2 overflow-y-auto">
            {filings.length === 0 && <li className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600">No filings yet. File one from <a href="/grievance" className="font-semibold text-navy-700 underline">Report a problem</a>.</li>}
            {filings.slice(0, 8).map((r, i) => (
              <motion.li key={r.reference_no} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }} className="rounded-xl bg-slate-50 p-3">
                <div className="flex items-center justify-between gap-2"><span className="font-mono text-xs font-bold text-navy-800">{r.reference_no}</span><Badge tone="navy"><Bot className="size-3" />Agent</Badge></div>
                <p className="mt-1 text-sm text-slate-700">{r.category} · {r.district ?? "location not shared"}</p>
                <p className="text-xs text-slate-500">Filed in {secs(r.timing.agent_ms)} of agent time · {new Date(r.created_at).toLocaleString()}</p>
              </motion.li>
            ))}
          </ol>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        {reports ? (
          <div className="grid gap-3 sm:grid-cols-4">
            {COLUMNS.map((col) => {
              const items = reports.filter((r) => col.match.includes(r.status));
              return (
                <div key={col.id} className="rounded-2xl bg-white/70 p-3 ring-1 ring-navy-100">
                  <div className="mb-2 flex items-center justify-between text-sm font-bold text-navy-900">{col.label}<span className="rounded-full bg-navy-50 px-2 text-xs">{items.length}</span></div>
                  <div className="space-y-2">
                    {items.slice(0, 6).map((r) => (
                      <motion.div key={r.code} layout className={`rounded-xl bg-white p-2.5 text-xs shadow-sm ring-1 ${r.sla_breached ? "ring-red-300" : "ring-navy-100"}`}>
                        <div className="flex items-center justify-between font-mono font-bold">{r.code}<span className="size-2.5 rounded-full" style={{ background: SEV_COLOR[r.severity] }} /></div>
                        <div className="mt-1 text-slate-600">{r.category}</div>
                        {r.source === "agent" && <Badge tone="navy" className="mt-1"><Bot className="size-3" />Agent</Badge>}
                      </motion.div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          config && <NotConnected part="The grievance pipeline (Part 2)" endpoint="PART2_API_URL" what="Its reports flow through Submitted, Routed, In progress and Resolved here, with deadlines and severity." />
        )}
        <Card variant="glass" className="p-5">
          <h2 className="text-lg font-extrabold text-navy-900">By category</h2>
          <ul className="mt-4 space-y-3">
            {byCategory.length === 0 && <li className="text-sm text-slate-600">No reports yet.</li>}
            {byCategory.map(([c, n]) => (
              <li key={c}>
                <div className="flex justify-between text-sm"><span className="font-medium text-slate-700">{c}</span><span className="font-mono text-slate-500">{n}</span></div>
                <div className="mt-1 h-2.5 overflow-hidden rounded-full bg-navy-50"><motion.div className="h-full origin-left rounded-full bg-gradient-to-r from-saffron-500 to-leaf-500" style={{ width: `${(n / maxCat) * 100}%` }} initial={{ scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true }} transition={{ duration: 0.6 }} /></div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
