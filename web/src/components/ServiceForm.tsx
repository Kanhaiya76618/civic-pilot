import { AnimatePresence, motion } from "motion/react";
import { BadgeCheck, CircleAlert, FileText, KeyRound, LoaderCircle, MapPin, ShieldCheck, Upload } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, type InputDef, type Service } from "../api";
import { Button, useToast } from "./ui";

type Props = {
  service: Service;
  prefill?: Record<string, string>;
  hide?: string[];
  extraFiles?: { key: string; file: File }[];
  submitLabel?: string;
  compact?: boolean;
  compactCard?: boolean;
  districts?: string[];
  cardTitle?: string;
  /** Called with the new task before the page moves to its agent room. */
  onStarted?: (r: { task_id: string; citizen_path: string }) => Promise<unknown> | void;
};

const field = "mt-1.5 w-full min-h-11 rounded-xl border border-navy-100 bg-white/90 px-3.5 py-2.5 text-base text-slate-900 shadow-inner shadow-navy-900/5 outline-none transition focus:border-navy-400 focus:ring-4 focus:ring-navy-100";

function inputType(i: InputDef) {
  if (i.key === "dob") return "date";
  if (/(^|_)(age|income|percentage)$/.test(i.key) || i.key === "annual_income") return "number";
  if (i.key === "email") return "email";
  if (i.key === "mobile") return "tel";
  return "text";
}

export function ServiceForm({ service, prefill = {}, hide = [], extraFiles = [], submitLabel = "Start", compact, compactCard, districts, cardTitle, onStarted }: Props) {
  const nav = useNavigate();
  const toast = useToast();
  const [values, setValues] = useState<Record<string, string>>(prefill);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [files, setFiles] = useState<Record<string, File>>({});
  const [consent, setConsent] = useState(false);
  const [mode, setMode] = useState(
    compactCard && service.submission_enabled && service.status === "stable"
      ? "assist"
      : service.read_only ? "assist" : "dry_run"
  );
  const [strategy, setStrategy] = useState(service.has_recorded_route ? "route" : "explore");
  const [busy, setBusy] = useState(false);
  const [pin, setPin] = useState(prefill.pincode ?? "");
  const [pinInfo, setPinInfo] = useState<{ ok: boolean | null; text: string; districts?: string[] } | null>(null);
  const [ifscInfo, setIfscInfo] = useState<{ ok: boolean | null; text: string } | null>(null);

  useEffect(() => { setValues((v) => ({ ...prefill, ...v })); }, [JSON.stringify(prefill)]); // eslint-disable-line react-hooks/exhaustive-deps
  const shown = useMemo(() => service.inputs.filter((i) => !hide.includes(i.key) && i.key !== "pincode"), [service, hide]);
  const pub = shown.filter((i) => i.source === "input" && (!compactCard || i.required || i.key === "district"));
  const priv = shown.filter((i) => i.source === "vault");
  const keys = new Set(service.inputs.map((i) => i.key));
  const wantsPin = keys.has("state") && !hide.includes("state");
  const set = (k: string, v: string) => { setValues((x) => ({ ...x, [k]: v })); setErrors((e) => ({ ...e, [k]: "" })); };

  // PIN code -> state and district, live from India Post data.
  useEffect(() => {
    if (!/^[1-9]\d{5}$/.test(pin)) { setPinInfo(null); return; }
    let live = true;
    setPinInfo({ ok: null, text: "Looking up your PIN code…" });
    api.pincode(pin).then((r) => {
      if (!live) return;
      if (!r.ok) { setPinInfo({ ok: r.ok, text: r.ok === false ? r.error ?? "PIN code not found" : "Lookup unavailable right now; type your state." }); return; }
      const st = service.inputs.find((i) => i.key === "state");
      const state = st?.enum?.find((e) => e.toLowerCase().replace("&", "and") === String(r.data.state).toLowerCase().replace("&", "and")) ?? r.data.state;
      const autodis: Record<string, string> = (keys.has("district") && r.data.districts.length === 1 && !values.district) ? { district: r.data.districts[0] } : {};
      setValues((v) => ({ ...v, state, ...autodis, ...(keys.has("pincode") ? { pincode: pin } : {}) }));
      setPinInfo({ ok: true, text: `${r.data.districts.join(", ")}, ${r.data.state}`, districts: r.data.districts });
    }).catch(() => live && setPinInfo({ ok: null, text: "Lookup unavailable right now; type your state." }));
    return () => { live = false; };
  }, [pin]); // eslint-disable-line react-hooks/exhaustive-deps

  // IFSC -> bank and branch, live from RBI IFSC data.
  useEffect(() => {
    const code = (values.ifsc ?? "").toUpperCase();
    if (code.length !== 11) { setIfscInfo(null); return; }
    let live = true;
    setIfscInfo({ ok: null, text: "Checking IFSC…" });
    api.ifsc(code).then((r) => live && setIfscInfo({ ok: r.ok, text: r.ok ? `${r.data.bank}, ${r.data.branch} branch` : r.ok === false ? r.error ?? "Not a valid IFSC" : "Could not check right now" }))
      .catch(() => live && setIfscInfo({ ok: null, text: "Could not check right now" }));
    return () => { live = false; };
  }, [values.ifsc]);

  function validate() {
    const errs: Record<string, string> = {};
    for (const i of service.inputs) {
      if (hide.includes(i.key) && !values[i.key]) continue;
      const v = (values[i.key] ?? "").trim();
      if (!v) { if (i.required) errs[i.key] = "This is required"; continue; }
      if (i.pattern && !new RegExp(`^(?:${i.pattern})$`).test(i.key === "ifsc" ? v.toUpperCase() : v)) errs[i.key] = "Please check the format";
      if (i.enum && !i.enum.includes(v)) errs[i.key] = "Choose one of the options";
    }
    for (const d of service.documents) if (d.required && !files[d.key] && !extraFiles.find((f) => f.key === d.key)) errs[`doc_${d.key}`] = "Please attach this document";
    if (!consent) errs.consent = "Please give consent to continue";
    setErrors(errs);
    const first = Object.keys(errs)[0];
    if (first) document.getElementById(`f_${first.replace(/^doc_/, "d_")}`)?.focus();
    return !first;
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setBusy(true);
    const inputs: Record<string, string> = {}, privateFields: Record<string, string> = {};
    for (const i of service.inputs) {
      const v = (values[i.key] ?? "").trim();
      if (!v) continue;
      (i.source === "vault" ? privateFields : inputs)[i.key] = i.key === "ifsc" ? v.toUpperCase() : v;
    }
    try {
      const fileList = [...Object.entries(files).map(([key, file]) => ({ key, file })), ...extraFiles];
      const r = await api.start({ portal_id: service.portal_id, service_id: service.service_id, inputs, private: privateFields, consent, mode, strategy, language: navigator.language }, fileList);
      toast("ok", "Started. Watch the agent work.");
      await Promise.resolve(onStarted?.(r)).catch(() => {});
      nav(r.citizen_path);
    } catch (err) {
      toast("error", (err as Error).message);
      setBusy(false);
    }
  }

  const Err = ({ k }: { k: string }) => (
    <AnimatePresence>{errors[k] && <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} role="alert" className="mt-1 flex items-center gap-1 text-sm font-medium text-red-700"><CircleAlert className="size-4" />{errors[k]}</motion.p>}</AnimatePresence>
  );

  const renderInput = (i: InputDef) => {
    const id = `f_${i.key}`;
    const label = (
      <label htmlFor={id} className="text-sm font-semibold text-navy-900">
        {i.label ?? i.key}{i.required ? <span className="text-red-600"> *</span> : <span className="font-normal text-slate-500"> (optional)</span>}
      </label>
    );
    const v = values[i.key] ?? "";
    let control;
    const availDistricts = pinInfo?.districts || districts;
    if (i.key === "district" && availDistricts && availDistricts.length > 1) {
      control = (
        <select id={id} className={field} value={v} onChange={(e) => set(i.key, e.target.value)} aria-invalid={!!errors[i.key]}>
          <option value="">Select district…</option>
          {availDistricts.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
      );
    } else if (i.enum) {
      control = (
        <select id={id} className={field} value={v} onChange={(e) => set(i.key, e.target.value)} aria-invalid={!!errors[i.key]}>
          <option value="">Select…</option>
          {i.enum.map((o) => <option key={o}>{o}</option>)}
        </select>
      );
    } else if (i.free_text && i.max_len > 200) {
      control = <textarea id={id} className={`${field} min-h-28`} maxLength={i.max_len} value={v} onChange={(e) => set(i.key, e.target.value)} aria-invalid={!!errors[i.key]} />;
    } else {
      control = <input id={id} className={field} type={inputType(i)} maxLength={i.max_len} value={v} autoComplete={i.source === "vault" ? "off" : undefined}
        inputMode={["mobile", "bank_account"].includes(i.key) ? "numeric" : undefined} onChange={(e) => set(i.key, e.target.value)} aria-invalid={!!errors[i.key]} />;
    }
    return (
      <div key={i.key} className={i.free_text && i.max_len > 200 ? "sm:col-span-2" : ""}>
        {label}{control}
        {i.key === "ifsc" && ifscInfo && (
          <p className={`mt-1 flex items-center gap-1 text-sm ${ifscInfo.ok ? "text-leaf-700" : ifscInfo.ok === false ? "text-red-700" : "text-slate-500"}`}>
            {ifscInfo.ok === null ? <LoaderCircle className="size-4 animate-spin" /> : ifscInfo.ok ? <BadgeCheck className="size-4" /> : <CircleAlert className="size-4" />}
            {ifscInfo.text}{ifscInfo.ok && <span className="text-slate-500"> · live RBI data</span>}
          </p>
        )}
        <Err k={i.key} />
      </div>
    );
  };

  if (compactCard) {
    return (
      <form onSubmit={submit} noValidate className="space-y-5 rounded-2xl bg-white p-5 ring-1 ring-navy-100 shadow-sm sm:p-6">
        <div>
          <h3 className="text-lg font-extrabold text-navy-900">{cardTitle || "I need only this from you"}</h3>
          <p className="mt-1 text-sm text-slate-600">The rest was filled from your request. Private fields are encrypted in the vault.</p>
        </div>

        {pub.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2">
            {pub.map(renderInput)}
          </div>
        )}

        {priv.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2">
            {priv.map(renderInput)}
          </div>
        )}

        <div>
          <label className="flex items-start gap-3 rounded-2xl bg-leaf-50/70 p-4 text-sm text-slate-700 ring-1 ring-leaf-200">
            <input id="f_consent" type="checkbox" className="mt-0.5 size-5 accent-[#138808]" checked={consent} onChange={(e) => { setConsent(e.target.checked); setErrors((x) => ({ ...x, consent: "" })); }} />
            <span><ShieldCheck className="mr-1 inline size-4 text-leaf-700" />I agree that Civic Pulse may fill <b>{service.description}</b> on <b>{service.portal_name}</b> for me during the next 24 hours. Nothing is submitted without my approval.</span>
          </label>
          <Err k="consent" />
        </div>

        <Button type="submit" variant="saffron" loading={busy} className="w-full text-base sm:w-auto">{submitLabel || "Start filing"}</Button>
      </form>
    );
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-6">
      {wantsPin && (
        <div className="rounded-2xl bg-saffron-50/80 p-4 ring-1 ring-saffron-200">
          <label htmlFor="f_pin" className="flex items-center gap-2 text-sm font-semibold text-navy-900"><MapPin className="size-4 text-saffron-700" /> Your PIN code <span className="font-normal text-slate-600">(fills your state{keys.has("district") ? " and district" : ""})</span></label>
          <input id="f_pin" className={field} inputMode="numeric" maxLength={6} placeholder="e.g. 823001" value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))} />
          {pinInfo && (
            <p className={`mt-1.5 flex items-center gap-1 text-sm ${pinInfo.ok ? "text-leaf-700" : pinInfo.ok === false ? "text-red-700" : "text-slate-600"}`}>
              {pinInfo.ok === null ? <LoaderCircle className="size-4 animate-spin" /> : pinInfo.ok ? <BadgeCheck className="size-4" /> : <CircleAlert className="size-4" />}
              {pinInfo.text}{pinInfo.ok && <span className="text-slate-500"> · live India Post data</span>}
            </p>
          )}
        </div>
      )}

      <div className={`grid gap-4 ${compact ? "" : "sm:grid-cols-2"}`}>{pub.map(renderInput)}</div>

      {priv.length > 0 && (
        <fieldset className="rounded-2xl border border-dashed border-navy-200 bg-navy-50/50 p-4">
          <legend className="flex items-center gap-2 px-2 text-sm font-bold text-navy-900"><KeyRound className="size-4" /> Private details</legend>
          <p className="mb-3 text-sm text-slate-600">Encrypted in a vault. The AI never sees these; only the browser step that types them does.</p>
          <div className="grid gap-4 sm:grid-cols-2">{priv.map(renderInput)}</div>
        </fieldset>
      )}

      {service.documents.filter((d) => !extraFiles.find((f) => f.key === d.key)).length > 0 && (
        <fieldset className="rounded-2xl border border-navy-100 bg-white/70 p-4">
          <legend className="flex items-center gap-2 px-2 text-sm font-bold text-navy-900"><FileText className="size-4" /> Documents</legend>
          <p className="mb-3 text-sm text-slate-600">Photos are resized automatically to the portal's size limit.</p>
          <div className="grid gap-4 sm:grid-cols-2">
            {service.documents.filter((d) => !extraFiles.find((f) => f.key === d.key)).map((d) => (
              <div key={d.key}>
                <label htmlFor={`d_${d.key}`} className="text-sm font-semibold text-navy-900">{d.label ?? d.key}{d.required ? <span className="text-red-600"> *</span> : <span className="font-normal text-slate-500"> (optional)</span>}</label>
                <label className="mt-1.5 flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border border-dashed border-navy-200 bg-white px-3 py-2.5 text-sm text-slate-600 hover:border-navy-400">
                  <Upload className="size-4 text-navy-600" />
                  <span className="truncate">{files[d.key]?.name ?? `Choose ${d.formats.join(" or ").toUpperCase()} (portal limit ${d.max_kb} KB)`}</span>
                  <input id={`d_${d.key}`} type="file" className="sr-only" accept={d.formats.map((f) => (f === "jpg" ? ".jpg,.jpeg,.png" : `.${f}`)).join(",")}
                    onChange={(e) => { const f = e.target.files?.[0]; if (f) { setFiles((x) => ({ ...x, [d.key]: f })); setErrors((er) => ({ ...er, [`doc_${d.key}`]: "" })); } }} />
                </label>
                <Err k={`doc_${d.key}`} />
              </div>
            ))}
          </div>
        </fieldset>
      )}

      {(!service.read_only || (service.explorable && service.has_recorded_route)) && (
        <div className="grid gap-4 sm:grid-cols-2">
          {!service.read_only && (
            <div>
              <label htmlFor="f_mode" className="text-sm font-semibold text-navy-900">What should happen</label>
              <select id="f_mode" className={field} value={mode} onChange={(e) => setMode(e.target.value)}>
                <option value="dry_run">Dry run: stop before submitting</option>
                {service.submission_enabled && service.status === "stable" && <option value="assist">File it after I approve</option>}
              </select>
            </div>
          )}
          {service.explorable && service.has_recorded_route && (
            <div>
              <label htmlFor="f_strategy" className="text-sm font-semibold text-navy-900">How the agent works</label>
              <select id="f_strategy" className={field} value={strategy} onChange={(e) => setStrategy(e.target.value)}>
                <option value="route">Replay the learned route (fast, no AI calls)</option>
                <option value="explore">Let the AI explore live (shows its reasoning)</option>
              </select>
            </div>
          )}
        </div>
      )}

      <div>
        <label className="flex items-start gap-3 rounded-2xl bg-leaf-50/70 p-4 text-sm text-slate-700 ring-1 ring-leaf-200">
          <input id="f_consent" type="checkbox" className="mt-0.5 size-5 accent-[#138808]" checked={consent} onChange={(e) => { setConsent(e.target.checked); setErrors((x) => ({ ...x, consent: "" })); }} />
          <span><ShieldCheck className="mr-1 inline size-4 text-leaf-700" />I agree that Civic Pulse may fill <b>{service.description}</b> on <b>{service.portal_name}</b> for me during the next 24 hours. Nothing is submitted without my approval.</span>
        </label>
        <Err k="consent" />
      </div>

      <Button type="submit" variant="saffron" loading={busy} className="w-full text-base sm:w-auto">{submitLabel}</Button>
    </form>
  );
}
