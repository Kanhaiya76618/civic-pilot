import { Building2, CircleAlert, Clock, Languages, LoaderCircle, MapPin, ScanSearch, ShieldAlert } from "lucide-react";
import { useState } from "react";
import type { Heard, ReportPreview } from "../api";
import { Badge } from "./ui";

/** What the pothole model and photo checks found, in the citizen's language when we know it. */
export function PhotoFindings({ data, busy, labelOf, onSwitch }: { data: ReportPreview | null; busy: boolean; labelOf?: (c: string) => string; onSwitch?: (c: string) => void }) {
  const [english, setEnglish] = useState(false);
  if (busy) return <p className="flex items-center gap-2 rounded-2xl bg-white p-4 text-sm text-slate-600 ring-1 ring-navy-100"><LoaderCircle className="size-4 animate-spin" />Checking your photo for potholes…</p>;
  if (!data?.findings.length) return null;
  const local = !english && data.findings_local?.length ? data.findings_local : null;
  const cc = data.category_check;
  const name = (c: string) => (labelOf ? labelOf(c) : c);
  return (
    <div className="rounded-2xl bg-white p-4 ring-1 ring-navy-100">
      {cc && !cc.matches && (
        <div role="alert" className="mb-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200">
          <p className="flex items-start gap-2 font-semibold"><CircleAlert className="mt-0.5 size-4 shrink-0" />This photo looks like <b>{name(cc.likely_category)}</b>{cc.issue ? ` (${cc.issue})` : ""}, not {name(cc.chosen)}.</p>
          {onSwitch && <button type="button" onClick={() => onSwitch(cc.likely_category)} className="mt-2 rounded-lg bg-white px-3 py-1.5 font-semibold text-navy-800 ring-1 ring-amber-300 hover:bg-amber-100">Switch to {name(cc.likely_category)}</button>}
        </div>
      )}
      {cc && cc.matches && !cc.problem_visible && <p className="mb-3 rounded-xl bg-slate-50 p-3 text-sm text-slate-700 ring-1 ring-slate-200">We could not see a clear problem in this photo. You can still report it; a closer photo helps the officer.</p>}
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-sm font-bold text-navy-900"><ScanSearch className="size-4 text-saffron-600" />What our photo check sees</p>
        {data.findings_local?.length ? <button type="button" onClick={() => setEnglish(!english)} className="text-xs font-semibold text-navy-700 hover:underline">{english ? "Your language" : "English"}</button> : null}
      </div>
      <ul className="mt-2 space-y-1.5 text-sm text-slate-700">
        {(local ?? data.findings).map((f, i) => <li key={i} className="flex gap-2"><span className="mt-2 size-1.5 shrink-0 rounded-full bg-saffron-500" />{f}</li>)}
      </ul>
      <p className="mt-2 text-xs text-slate-500">{local ? "Machine-translated. " : ""}AI photo check{data.perception.method === "yolo" ? " and our pothole model" : ""}; the municipal officer checks it too.</p>
    </div>
  );
}

/** The voice note as text, in the language and script it was spoken in. The citizen can correct it. */
export function SpokenText({ heard, busy, value, onChange }: { heard: Heard | null; busy: boolean; value: string; onChange: (v: string) => void }) {
  if (busy) return <p className="flex items-center gap-2 rounded-2xl bg-white p-4 text-sm text-slate-600 ring-1 ring-navy-100"><LoaderCircle className="size-4 animate-spin" />Writing down what you said…</p>;
  if (!heard) return null;
  return (
    <div className="rounded-2xl bg-white p-4 ring-1 ring-navy-100">
      <label htmlFor="g_heard" className="flex flex-wrap items-center gap-2 text-sm font-bold text-navy-900">
        <Languages className="size-4 text-violet-600" />What you said{heard.language_name && <Badge tone="blue">{heard.language_name}</Badge>}
      </label>
      <textarea id="g_heard" dir="auto" className="mt-2 min-h-24 w-full rounded-xl border border-navy-100 bg-white p-3 text-base outline-none focus:border-navy-400 focus:ring-4 focus:ring-navy-100" value={value} onChange={(e) => onChange(e.target.value)} maxLength={4000} />
      <p className="mt-1 text-xs text-slate-500">Correct anything we misheard. This goes into your report in your own words; the officer also gets an English translation.</p>
    </div>
  );
}

/** Where the report will go and how urgent it is, before anything is filed. */
export function ReviewPanel({ data, busy }: { data: ReportPreview | null; busy: boolean }) {
  const [english, setEnglish] = useState(false);
  if (busy) return <p className="flex items-center gap-2 rounded-2xl bg-white p-5 text-slate-600 ring-1 ring-navy-100"><LoaderCircle className="size-4 animate-spin" />Working out the department, ward and deadline…</p>;
  if (!data?.severity) return null;
  const tone = data.severity === "P1" ? "red" : data.severity === "P2" ? "saffron" : "leaf";
  const reasons = !english && data.reasons_local?.length ? data.reasons_local : data.reasons ?? [];
  return (
    <div className="space-y-3 rounded-2xl bg-white p-5 ring-1 ring-navy-100">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={tone}>Urgency: {data.severity_name}</Badge>
        <Badge tone="navy"><Building2 className="size-3" />{data.department}</Badge>
        <Badge tone="gray"><Clock className="size-3" />Due within {data.sla_hours} h</Badge>
        {data.reasons_local?.length ? <button type="button" onClick={() => setEnglish(!english)} className="ml-auto text-xs font-semibold text-navy-700 hover:underline">{english ? "Your language" : "English"}</button> : null}
      </div>
      <ul className="space-y-1 text-sm text-slate-700">{reasons.map((r, i) => <li key={i} className="flex gap-2"><ShieldAlert className="mt-0.5 size-4 shrink-0 text-saffron-600" />{r}</li>)}</ul>
      <p className="flex items-center gap-1.5 text-sm text-slate-600"><MapPin className="size-4" />{data.ward_id === "UNMAPPED" ? `${data.city} (this area's ward map is not loaded yet)` : `${data.ward_name}, ${data.city}`}</p>
      {data.nearby_report && (
        <p className="flex items-start gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200">
          <CircleAlert className="mt-0.5 size-4 shrink-0" />Someone already reported this {data.nearby_report.distance_m} m away ({data.nearby_report.ticket}). Yours will be linked to it, which raises its priority.
        </p>
      )}
    </div>
  );
}
