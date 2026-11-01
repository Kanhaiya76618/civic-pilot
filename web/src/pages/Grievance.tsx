import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, ArrowRight, BadgeCheck, Camera, CircleAlert, Crosshair, LoaderCircle, MapPin, Mic, Route, Sparkles, Square, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { CircleMarker, MapContainer, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { api, type AppConfig, type Service } from "../api";
import { CategoryArt, type Category } from "../components/Illustrations";
import { ServiceForm } from "../components/ServiceForm";
import { Badge, Button, Card, fadeUp, SectionTitle, stagger, useToast } from "../components/ui";

const CATEGORIES: { id: Category; label: string; hi: string; tint: string }[] = [
  { id: "Road and Bridges", label: "Roads & bridges", hi: "सड़क", tint: "from-slate-100" },
  { id: "Water Supply", label: "Water supply", hi: "पानी", tint: "from-sky-50" },
  { id: "Sanitation and Garbage", label: "Garbage & drains", hi: "सफ़ाई", tint: "from-leaf-50" },
  { id: "Street Lights", label: "Street lights", hi: "बिजली", tint: "from-amber-50" },
  { id: "Pollution", label: "Pollution", hi: "प्रदूषण", tint: "from-zinc-100" },
  { id: "Other", label: "Something else", hi: "अन्य", tint: "from-navy-50" },
];

/** Part 2 contract: POST /api/reports (multipart) -> Triage (see docs/UI_CONTRACT.md). */
type Triage = { code?: string; severity: "P1" | "P2" | "P3" | string; category?: string; reasoning?: string; duplicate_of?: string | null };

const STEPS = ["Photo & voice", "Location", "Details", "Review & file"];
const field = "mt-1.5 w-full min-h-11 rounded-xl border border-navy-100 bg-white px-3.5 py-2.5 text-base outline-none focus:border-navy-400 focus:ring-4 focus:ring-navy-100";

function Recenter({ at }: { at: [number, number] }) {
  const map = useMap();
  useEffect(() => { map.setView(at, 15); }, [at, map]);
  return null;
}

function VoiceNote({ value, onChange }: { value: Blob | null; onChange: (b: Blob | null) => void }) {
  const [rec, setRec] = useState<MediaRecorder | null>(null);
  const [seconds, setSeconds] = useState(0);
  const toast = useToast();
  useEffect(() => { if (!rec) return; const t = setInterval(() => setSeconds((s) => s + 1), 1000); return () => clearInterval(t); }, [rec]);
  const url = value ? URL.createObjectURL(value) : null;
  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      const parts: Blob[] = [];
      mr.ondataavailable = (e) => parts.push(e.data);
      mr.onstop = () => { onChange(new Blob(parts, { type: mr.mimeType })); stream.getTracks().forEach((t) => t.stop()); setRec(null); };
      mr.start(); setSeconds(0); setRec(mr);
    } catch { toast("error", "Microphone not available. You can type instead."); }
  };
  return (
    <div className="rounded-2xl bg-white p-4 ring-1 ring-navy-100">
      <p className="text-sm font-semibold text-navy-900">Voice note <span className="font-normal text-slate-500">(optional, any language)</span></p>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        {rec ? (
          <Button variant="danger" onClick={() => rec.stop()}><Square className="size-4" />Stop · {seconds}s</Button>
        ) : (
          <Button variant="secondary" onClick={start}><Mic className="size-4" />{value ? "Record again" : "Record"}</Button>
        )}
        {rec && <span className="flex items-center gap-1" aria-hidden>{Array.from({ length: 12 }).map((_, i) => <motion.span key={i} className="w-1 rounded-full bg-saffron-500" animate={{ height: [6, 18 - (i % 4) * 3, 6] }} transition={{ duration: 0.5 + (i % 3) * 0.15, repeat: Infinity }} />)}</span>}
        {url && !rec && <><audio src={url} controls className="h-10 max-w-full" /><button className="rounded-lg p-2 text-slate-500 hover:bg-red-50 hover:text-red-600" aria-label="Delete voice note" onClick={() => onChange(null)}><Trash2 className="size-4" /></button></>}
      </div>
    </div>
  );
}

export default function Grievance() {
  const toast = useToast();
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [service, setService] = useState<Service | null>(null);
  const [step, setStep] = useState(0);
  const [category, setCategory] = useState<Category | null>(null);
  const [photo, setPhoto] = useState<File | null>(null);
  const [voice, setVoice] = useState<Blob | null>(null);
  const [coords, setCoords] = useState<[number, number] | null>(null);
  const [pin, setPin] = useState("");
  const [place, setPlace] = useState<{ state: string; district: string; districts: string[] } | null>(null);
  const [locBusy, setLocBusy] = useState(false);
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [triage, setTriage] = useState<Triage | null>(null);
  const [triageBusy, setTriageBusy] = useState(false);
  const flowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.config().then(setConfig).catch(() => {});
    api.services().then((s) => setService(s.find((x) => x.portal_id === "sandbox" && x.service_id === "public_grievance") ?? null)).catch(() => {});
  }, []);

  // PIN code -> district and state from India Post (live).
  useEffect(() => {
    if (!/^[1-9]\d{5}$/.test(pin)) return;
    api.pincode(pin).then((r) => {
      if (r.ok) setPlace({ state: r.data.state, district: r.data.districts[0], districts: r.data.districts });
      else if (r.ok === false) toast("error", r.error ?? "PIN code not found");
    }).catch(() => {});
  }, [pin]); // eslint-disable-line react-hooks/exhaustive-deps

  const choose = (c: Category) => { setCategory(c); setStep(0); setTimeout(() => flowRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50); };

  const locate = () => {
    if (!navigator.geolocation) { toast("error", "Location is not available on this device. Type your PIN code instead."); return; }
    setLocBusy(true);
    navigator.geolocation.getCurrentPosition(async (pos) => {
      const at: [number, number] = [pos.coords.latitude, pos.coords.longitude];
      setCoords(at);
      try { // OpenStreetMap reverse geocoding: only the postcode is kept, then checked against India Post data.
        const r = await fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=16&lat=${at[0]}&lon=${at[1]}`, { headers: { "Accept-Language": "en" } });
        const j = await r.json();
        const pc = String(j?.address?.postcode ?? "").replace(/\s/g, "");
        if (/^[1-9]\d{5}$/.test(pc)) setPin(pc); else toast("warn", "Could not find a PIN code here. Please type it.");
      } catch { toast("warn", "Could not look up the area. Please type your PIN code."); }
      setLocBusy(false);
    }, () => { setLocBusy(false); toast("error", "Location permission was denied. Type your PIN code instead."); }, { enableHighAccuracy: true, timeout: 12000 });
  };

  async function runTriage() {
    if (!config?.part2_connected || !category) return;
    setTriageBusy(true);
    try {
      const fd = new FormData();
      if (photo) fd.append("photo", photo);
      if (voice) fd.append("audio", voice, "voice-note.webm");
      fd.append("category", category); fd.append("description", description);
      if (coords) { fd.append("lat", String(coords[0])); fd.append("lng", String(coords[1])); }
      setTriage(await api.part2("api/reports", { method: "POST", body: fd }));
    } catch (e) { toast("error", (e as Error).message); }
    setTriageBusy(false);
  }
  useEffect(() => { if (step === 3) runTriage(); }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  const canNext = [true, !!place, subject.trim().length >= 5 && description.trim().length >= 10, true][step];
  const photoUrl = photo ? URL.createObjectURL(photo) : null;
  const sev = triage?.severity === "P1" ? { label: "Critical", tone: "red" as const } : triage?.severity === "P2" ? { label: "High", tone: "saffron" as const } : { label: "Medium", tone: "leaf" as const };
  const routing = (category && service?.derive?.category?.[category]) || { ministry: "", department: "" };

  return (
    <div>
      <section className="mx-auto grid max-w-7xl items-center gap-10 px-4 pb-6 pt-10 lg:grid-cols-[1.1fr_1fr]">
        <motion.div initial="hidden" animate="show" variants={stagger}>
          <motion.div variants={fadeUp}><Badge tone="saffron">Part 2 · Grievance & triage</Badge></motion.div>
          <motion.h1 variants={fadeUp} className="mt-4 text-4xl font-extrabold leading-tight text-navy-900 sm:text-5xl">Report a civic problem. Track it until it's fixed.</motion.h1>
          <motion.p variants={fadeUp} className="mt-4 max-w-xl text-lg text-slate-700">Take a photo, say what's wrong, and we find the right department. Our agent files it on the grievance portal with your approval, and the reference number goes on the public board.</motion.p>
        </motion.div>
        <Card variant="clay" className="overflow-hidden bg-white p-2"><img src="/images/civic-reporting-guide-3d.webp" alt="A citizen photographs a pothole while municipal workers repair the road" className="aspect-[4/3] w-full rounded-[1.35rem] object-cover" /></Card>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-8" aria-labelledby="cat">
        <h2 id="cat" className="mb-5 text-2xl font-extrabold text-navy-900">What is the problem about?</h2>
        <motion.div initial="hidden" animate="show" variants={stagger} className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          {CATEGORIES.map((c) => (
            <motion.button key={c.id} variants={fadeUp} whileHover={{ y: -5 }} whileTap={{ scale: 0.97 }} onClick={() => choose(c.id)} aria-pressed={category === c.id}
              className={`clay flex flex-col items-center gap-2 bg-gradient-to-b ${c.tint} to-white p-4 text-center ${category === c.id ? "ring-4 ring-saffron-400" : ""}`}>
              <CategoryArt category={c.id} className="size-20" />
              <span className="font-bold text-navy-900">{c.label}</span>
              <span className="text-sm text-slate-500">{c.hi}</span>
            </motion.button>
          ))}
        </motion.div>
      </section>

      <AnimatePresence>
        {category && (
          <motion.section ref={flowRef} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mx-auto max-w-4xl scroll-mt-28 px-4 py-6">
            <Card variant="glass" className="p-5 sm:p-8">
              <ol className="mb-8 grid grid-cols-4 gap-2" aria-label="Progress">
                {STEPS.map((s, i) => (
                  <li key={s} className="text-center">
                    <div className={`mx-auto mb-1.5 h-1.5 rounded-full ${i <= step ? "tricolor-bar" : "bg-navy-100"}`} />
                    <span className={`text-xs font-semibold sm:text-sm ${i === step ? "text-navy-900" : "text-slate-500"}`}>{i + 1}. {s}</span>
                  </li>
                ))}
              </ol>

              <AnimatePresence mode="wait">
                <motion.div key={step} initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }} transition={{ duration: 0.22 }}>
                  {step === 0 && (
                    <div className="grid gap-5 sm:grid-cols-2">
                      <label className="flex min-h-56 cursor-pointer flex-col items-center justify-center gap-3 overflow-hidden rounded-3xl border-2 border-dashed border-navy-200 bg-white text-center hover:border-saffron-400">
                        {photoUrl ? <img src={photoUrl} alt="Your photo of the problem" className="h-full max-h-72 w-full object-cover" /> : (
                          <><span className="grid size-16 place-items-center rounded-2xl bg-saffron-100 text-saffron-700"><Camera className="size-8" /></span>
                            <span className="font-bold text-navy-900">Take or choose a photo</span><span className="text-sm text-slate-500">Optional, but it helps. Resized automatically.</span></>
                        )}
                        <input type="file" accept="image/*" capture="environment" className="sr-only" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
                      </label>
                      <div className="space-y-4">
                        <VoiceNote value={voice} onChange={setVoice} />
                        <p className="rounded-2xl bg-navy-50 p-4 text-sm text-navy-800">Your photo and voice note go to the triage service, which estimates how urgent this is. The photo is also attached to the filing.</p>
                      </div>
                    </div>
                  )}

                  {step === 1 && (
                    <div className="grid gap-5 sm:grid-cols-2">
                      <div className="space-y-4">
                        <Button variant="primary" onClick={locate} loading={locBusy} className="w-full"><Crosshair className="size-4" />Use my current location</Button>
                        <div>
                          <label htmlFor="g_pin" className="text-sm font-semibold text-navy-900">Or type the PIN code</label>
                          <input id="g_pin" className={field} inputMode="numeric" maxLength={6} value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))} placeholder="e.g. 625001" />
                        </div>
                        {place && (
                          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl bg-leaf-50 p-4 ring-1 ring-leaf-200">
                            <p className="flex items-center gap-1.5 text-sm font-bold text-leaf-700"><BadgeCheck className="size-4" />Found with live India Post data</p>
                            <label htmlFor="g_district" className="mt-2 block text-sm font-semibold text-navy-900">District</label>
                            <select id="g_district" className={field} value={place.district} onChange={(e) => setPlace({ ...place, district: e.target.value })}>
                              {place.districts.map((d) => <option key={d}>{d}</option>)}
                            </select>
                            <p className="mt-2 text-sm text-slate-700">State: <b>{place.state}</b></p>
                          </motion.div>
                        )}
                        <p className="text-xs text-slate-500">"Use my location" asks OpenStreetMap for the PIN code of your spot. The public board shows locations rounded to about 1 km.</p>
                      </div>
                      <div className="min-h-64 overflow-hidden rounded-3xl ring-1 ring-navy-100">
                        {coords ? (
                          <MapContainer center={coords} zoom={15} scrollWheelZoom={false} className="h-full min-h-64 w-full">
                            <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                            <CircleMarker center={coords} radius={12} pathOptions={{ color: "#FF9933", fillColor: "#FF9933", fillOpacity: 0.6 }} />
                            <Recenter at={coords} />
                          </MapContainer>
                        ) : (
                          <div className="flex h-full min-h-64 flex-col items-center justify-center gap-2 bg-navy-50 text-center text-navy-700"><MapPin className="size-10 text-saffron-600" /><p className="font-semibold">Your spot will show here</p></div>
                        )}
                      </div>
                    </div>
                  )}

                  {step === 2 && (
                    <div className="space-y-4">
                      <div>
                        <label htmlFor="g_subject" className="text-sm font-semibold text-navy-900">Short title <span className="text-red-600">*</span></label>
                        <input id="g_subject" className={field} maxLength={150} value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g. Water pipe leaking on Station Road for 2 weeks" />
                      </div>
                      <div>
                        <label htmlFor="g_desc" className="text-sm font-semibold text-navy-900">What is happening? <span className="text-red-600">*</span></label>
                        <textarea id="g_desc" className={`${field} min-h-32`} maxLength={4000} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Where exactly, since when, and who is affected." />
                        <p className="mt-1 text-right text-xs text-slate-500">{description.length}/4000</p>
                      </div>
                      <div className="flex items-start gap-3 rounded-2xl bg-saffron-50 p-4 ring-1 ring-saffron-200">
                        <Route className="mt-0.5 size-5 shrink-0 text-saffron-700" />
                        <p className="text-sm text-navy-900">Will be sent to <b>{routing.ministry}</b> · {routing.department}</p>
                      </div>
                    </div>
                  )}

                  {step === 3 && service && (
                    <div className="space-y-6">
                      {config?.part2_connected ? (
                        <div className="relative overflow-hidden rounded-2xl bg-white p-5 ring-1 ring-navy-100">
                          {triageBusy && <div className="shimmer absolute inset-0" />}
                          <p className="flex items-center gap-2 text-sm font-bold text-navy-700"><Sparkles className="size-4 text-violet-600" />AI triage</p>
                          {triageBusy ? <p className="mt-2 flex items-center gap-2 text-slate-600"><LoaderCircle className="size-4 animate-spin" />Analysing your photo and description…</p> : triage && (
                            <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="mt-2 space-y-2">
                              <div className="flex flex-wrap items-center gap-2"><Badge tone={sev.tone}>Severity: {sev.label}</Badge>{triage.code && <Badge tone="gray">{triage.code}</Badge>}</div>
                              {triage.reasoning && <p className="text-slate-700">{triage.reasoning}</p>}
                              {triage.duplicate_of && <p className="flex items-center gap-1.5 text-sm font-semibold text-amber-700"><CircleAlert className="size-4" />Possible duplicate of {triage.duplicate_of}</p>}
                            </motion.div>
                          )}
                        </div>
                      ) : (
                        <p className="flex items-start gap-2 rounded-2xl bg-navy-50 p-4 text-sm text-navy-800"><Sparkles className="mt-0.5 size-4 shrink-0" />AI triage (Part 2) is not connected yet, so there is no severity estimate. You can still file now.</p>
                      )}
                      <dl className="grid gap-x-6 gap-y-2 rounded-2xl bg-white p-4 text-sm ring-1 ring-navy-100 sm:grid-cols-2">
                        {[["Category", category], ["Place", `${place?.district}, ${place?.state} ${pin}`], ["Title", subject], ["Photo", photo ? photo.name : "none"]].map(([k, v]) => (
                          <div key={k}><dt className="text-slate-500">{k}</dt><dd className="font-semibold text-slate-900">{v}</dd></div>
                        ))}
                      </dl>
                      <div className="rounded-2xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200">Filed on the <b>sandbox replica</b> of a CPGRAMS-style portal: real filings to ministries are never used for testing.</div>
                      <ServiceForm
                        service={service}
                        prefill={{ ministry: routing.ministry, department: routing.department, category, state: place?.state ?? "", district: place?.district ?? "", pincode: pin, subject, description, ...(coords ? { latitude: coords[0].toFixed(6), longitude: coords[1].toFixed(6) } : {}) }}
                        hide={["ministry", "department", "category", "state", "district", "subject", "description", "latitude", "longitude", "pincode"]}
                        extraFiles={photo ? [{ key: "attachment", file: photo }] : []}
                        submitLabel="File it with the agent"
                        compact
                      />
                    </div>
                  )}
                </motion.div>
              </AnimatePresence>

              {step < 3 && (
                <div className="mt-8 flex items-center justify-between gap-3">
                  <Button variant="ghost" disabled={step === 0} onClick={() => setStep(step - 1)}><ArrowLeft className="size-4" />Back</Button>
                  <Button variant="saffron" disabled={!canNext} onClick={() => setStep(step + 1)}>Continue<ArrowRight className="size-4" /></Button>
                </div>
              )}
              {step === 3 && <Button variant="ghost" className="mt-4" onClick={() => setStep(2)}><ArrowLeft className="size-4" />Back</Button>}
            </Card>
          </motion.section>
        )}
      </AnimatePresence>

      {!category && (
        <section className="mx-auto max-w-7xl px-4 py-8">
          <SectionTitle kicker="What happens next" title="From your photo to a reference number">Pick a category above to start. It takes about two minutes.</SectionTitle>
        </section>
      )}
    </div>
  );
}
