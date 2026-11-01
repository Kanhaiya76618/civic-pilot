import { motion } from "motion/react";
import { ArrowRight, Building2, CheckCircle2, CircleAlert, LockKeyhole, MapPinned, ShieldCheck, UserPlus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { type CivicRole, setAuthSession } from "../auth";
import { Badge, Button } from "../components/ui";

type LoginResponse = { access_token: string; user: { id: string; email: string; name: string; role: CivicRole } };
type ConfirmationResponse = { status: "confirmation_required"; message: string };

export default function SignIn() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const initial = params.get("role") === "admin" ? "admin" : "citizen";
  const [role, setRole] = useState<CivicRole>(initial);
  const [mode, setMode] = useState<"signin" | "signup">(initial === "admin" ? "signin" : "signup");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const next = params.get("next") || "";
  const safeNext = next.startsWith("/") && !next.startsWith("//") ? next : "";
  const chooseRole = (nextRole: CivicRole) => { setRole(nextRole); setConfirmation(""); setError(""); if (nextRole === "admin") setMode("signin"); };
  const setAuthMode = (nextMode: "signin" | "signup") => { setMode(nextMode); setConfirmation(""); setError(""); if (nextMode === "signup") setRole("citizen"); };
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setConfirmation("");
    try {
      const endpoint = mode === "signup" ? "/api/v1/auth/signup" : "/api/v1/auth/login";
      const payload = mode === "signup" ? { name, email, password } : { email, password };
      const response = await fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const data = await response.json() as LoginResponse | ConfirmationResponse | { detail?: string };
      if (response.status === 202 && "status" in data && data.status === "confirmation_required") { setConfirmation(data.message); return; }
      if (!response.ok || !("access_token" in data)) throw new Error("detail" in data ? data.detail : "We could not sign you in.");
      if (data.user.role !== role) throw new Error(role === "admin" ? "This account is not authorised for the municipal desk." : "Please choose the citizen workspace for this account.");
      setAuthSession({ token: data.access_token, user: data.user });
      navigate(role === "admin" ? "/admin" : (safeNext && !safeNext.startsWith("/admin") ? safeNext : "/home"), { replace: true });
    } catch (err) { setError((err as Error).message || "We could not sign you in."); }
    finally { setBusy(false); }
  }
  return <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 lg:grid-cols-[.9fr_1.1fr] lg:items-center lg:py-20">
    <section className="rounded-[2rem] bg-navy-800 p-8 text-white sm:p-10"><Badge tone="saffron">Choose the right workspace</Badge><h1 className="mt-5 text-4xl font-extrabold sm:text-5xl">A simpler door into civic work.</h1><p className="mt-4 max-w-md text-lg leading-8 text-navy-100">Citizen services and municipal operations have different responsibilities. Swayam-sevak keeps that distinction clear from the first screen.</p><div className="mt-10 space-y-5">{[[MapPinned, "Citizen workspace", "Discover schemes, report problems and work through a guided filing."], [Building2, "Municipal desk", "Review reports, correct triage, assign work and attach closure evidence."]].map(([Icon, title, body]) => <div key={String(title)} className="flex gap-4"><span className="grid size-10 shrink-0 place-items-center rounded-xl bg-white/10"><Icon className="size-5 text-saffron-300" /></span><div><h2 className="font-bold">{String(title)}</h2><p className="mt-1 text-sm leading-6 text-navy-100">{String(body)}</p></div></div>)}</div><div className="mt-10 flex items-center gap-2 text-xs text-navy-100"><ShieldCheck className="size-4 text-leaf-300" />Role is checked again by protected server actions.</div></section>
    <motion.form initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} onSubmit={submit} className="rounded-[2rem] bg-white p-7 shadow-[0_18px_50px_-25px_rgb(19_48_107/.35)] ring-1 ring-navy-100 sm:p-10"><div className="flex rounded-xl bg-slate-100 p-1"><button type="button" onClick={() => setAuthMode("signup")} aria-pressed={mode === "signup"} className={`flex min-h-10 flex-1 items-center justify-center gap-2 rounded-lg text-sm font-bold transition ${mode === "signup" ? "bg-white text-navy-900 shadow-sm" : "text-slate-600 hover:text-navy-900"}`}><UserPlus className="size-4" />Create account</button><button type="button" onClick={() => setAuthMode("signin")} aria-pressed={mode === "signin"} className={`flex min-h-10 flex-1 items-center justify-center gap-2 rounded-lg text-sm font-bold transition ${mode === "signin" ? "bg-white text-navy-900 shadow-sm" : "text-slate-600 hover:text-navy-900"}`}><LockKeyhole className="size-4" />Sign in</button></div><p className="mt-7 text-sm font-bold uppercase tracking-[.14em] text-saffron-700">{mode === "signup" ? "Citizen registration" : "Welcome back"}</p><h2 className="mt-2 text-3xl font-extrabold text-navy-900">{mode === "signup" ? "Create your Swayam-sevak account." : "Sign in to continue."}</h2><div className="mt-7 grid gap-3 sm:grid-cols-2"><button type="button" onClick={() => chooseRole("citizen")} aria-pressed={role === "citizen"} className={`rounded-2xl border p-4 text-left transition ${role === "citizen" ? "border-navy-500 bg-navy-50 ring-2 ring-navy-100" : "border-slate-200 hover:border-navy-200"}`}><MapPinned className="size-5 text-navy-700" /><div className="mt-3 font-bold text-navy-900">Citizen</div><p className="mt-1 text-xs leading-5 text-slate-600">I need a service or want to report an issue.</p></button><button type="button" onClick={() => chooseRole("admin")} aria-pressed={role === "admin"} className={`rounded-2xl border p-4 text-left transition ${role === "admin" ? "border-leaf-600 bg-leaf-50 ring-2 ring-leaf-100" : "border-slate-200 hover:border-leaf-200"}`}><Building2 className="size-5 text-leaf-700" /><div className="mt-3 font-bold text-navy-900">Municipal desk</div><p className="mt-1 text-xs leading-5 text-slate-600">Authorised officer sign-in only.</p></button></div>{role === "admin" && <p className="mt-4 rounded-xl bg-leaf-50 p-3 text-sm text-leaf-800">Municipal accounts are provisioned by the authority. Use the officer email and password you were issued.</p>}{mode === "signup" && <><label className="mt-6 block text-sm font-bold text-navy-900" htmlFor="name">Your name</label><input id="name" required autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Your full name" className="mt-2 min-h-12 w-full rounded-xl border border-navy-200 px-4 text-navy-900 outline-none transition placeholder:text-slate-400 focus:border-navy-500 focus:ring-4 focus:ring-navy-100" /></>}<label className="mt-6 block text-sm font-bold text-navy-900" htmlFor="email">Email address</label><input id="email" type="email" required autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder={role === "admin" ? "authorised municipal email" : "you@example.com"} className="mt-2 min-h-12 w-full rounded-xl border border-navy-200 px-4 text-navy-900 outline-none transition placeholder:text-slate-400 focus:border-navy-500 focus:ring-4 focus:ring-navy-100" /><label className="mt-5 block text-sm font-bold text-navy-900" htmlFor="password">Password</label><input id="password" type="password" required minLength={8} autoComplete={mode === "signup" ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="At least 8 characters" className="mt-2 min-h-12 w-full rounded-xl border border-navy-200 px-4 text-navy-900 outline-none transition placeholder:text-slate-400 focus:border-navy-500 focus:ring-4 focus:ring-navy-100" />{confirmation && <p role="status" className="mt-4 flex gap-2 rounded-xl bg-leaf-50 p-3 text-sm font-medium text-leaf-800"><CheckCircle2 className="mt-0.5 size-4 shrink-0" />{confirmation}</p>}{error && <p role="alert" className="mt-4 flex gap-2 rounded-xl bg-red-50 p-3 text-sm font-medium text-red-800"><CircleAlert className="mt-0.5 size-4 shrink-0" />{error}</p>}<Button type="submit" loading={busy} className="mt-7 w-full">{mode === "signup" ? "Create citizen account" : `Continue to ${role === "admin" ? "municipal desk" : "citizen workspace"}`}<ArrowRight className="size-4" /></Button><p className="mt-5 text-center text-xs leading-5 text-slate-500">Passwords are handled by Supabase Auth. Swayam-sevak stores only the profile and role needed for civic services.</p><Link to="/" className="mt-5 block text-center text-sm font-semibold text-navy-700 hover:underline">Back to Swayam-sevak</Link></motion.form>
  </div>;
}
