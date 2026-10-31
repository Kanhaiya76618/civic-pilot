import { motion, AnimatePresence } from "motion/react";
import {
  ShieldAlert, CheckCircle, Clock, ArrowRight, UserCheck, Filter,
  Building2, AlertTriangle, FileCheck, Upload, Send, ExternalLink,
  ChevronDown, RefreshCw, XCircle, MapPin, Eye, ThumbsUp
} from "lucide-react";
import { useEffect, useState, useMemo } from "react";
import { Badge, Button, Card, fadeUp, stagger, useToast } from "../components/ui";

type AdminReport = {
  id: string;
  category: string;
  description: string;
  severity: "P1" | "P2" | "P3" | "P4";
  status: string;
  ward_id: string;
  ward_name: string;
  city: string;
  latitude: number;
  longitude: number;
  sla_deadline: string | null;
  sla_breached: boolean;
  poi_multiplier: number;
  assigned_to: string | null;
  upvotes: number;
  duplicate_of: string | null;
  evidence_urls: string[];
  resolution_proof_url: string | null;
  created_at: string;
};

const SEV_BADGE = {
  P1: "bg-red-100 text-red-800 border-red-300 animate-pulse",
  P2: "bg-amber-100 text-amber-800 border-amber-300",
  P3: "bg-emerald-100 text-emerald-800 border-emerald-300",
  P4: "bg-slate-100 text-slate-800 border-slate-300"
};

export default function AdminDesk() {
  const toast = useToast();
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminUser, setAdminUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [reports, setReports] = useState<AdminReport[]>([]);
  const [token, setToken] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [wardFilter, setWardFilter] = useState<string>("ALL");
  const [sevFilter, setSevFilter] = useState<string>("ALL");

  // Resolve Modal state
  const [resolveTarget, setResolveTarget] = useState<AdminReport | null>(null);
  const [resolvePhoto, setResolvePhoto] = useState<File | null>(null);
  const [resolveNotes, setResolveNotes] = useState("");
  const [resolving, setResolving] = useState(false);

  // AutoFile State
  const [autofilingId, setAutofilingId] = useState<string | null>(null);

  // Quick Admin Login
  const loginAsAdmin = async () => {
    try {
      setLoading(true);
      const res = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "admin@demo.in" })
      });
      const data = await res.json();
      if (res.ok) {
        setToken(data.access_token);
        setIsAdmin(true);
        setAdminUser(data.user);
        toast("success", "Signed in as Municipal Desk Admin (Priya Nair)");
        fetchQueue(data.access_token);
      } else {
        toast("error", "Admin authentication failed");
      }
    } catch {
      toast("error", "Network error signing in");
    } finally {
      setLoading(false);
    }
  };

  const fetchQueue = async (authToken?: string) => {
    const t = authToken || token;
    try {
      setLoading(true);
      const headers: Record<string, string> = {};
      if (t) headers["Authorization"] = `Bearer ${t}`;
      const res = await fetch("/api/v1/admin/queue", { headers });
      if (res.status === 401) {
        setIsAdmin(false);
      } else if (res.ok) {
        const data = await res.json();
        setReports(data);
        setIsAdmin(true);
      }
    } catch {
      toast("error", "Failed to load triage queue");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Attempt automatic login with demo admin account
    loginAsAdmin();
  }, []);

  // Filtered reports
  const filtered = useMemo(() => {
    return reports.filter((r) => {
      if (statusFilter !== "ALL" && r.status !== statusFilter) return false;
      if (wardFilter !== "ALL" && r.ward_id !== wardFilter) return false;
      if (sevFilter !== "ALL" && r.severity !== sevFilter) return false;
      return true;
    });
  }, [reports, statusFilter, wardFilter, sevFilter]);

  // Actions
  const handleAcknowledge = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/admin/reports/${id}/acknowledge`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        toast("success", "Ticket Acknowledged");
        fetchQueue();
      }
    } catch {
      toast("error", "Action failed");
    }
  };

  const handleAssign = async (id: string, assignedTo: string) => {
    try {
      const fd = new FormData();
      fd.append("assigned_to", assignedTo);
      const res = await fetch(`/api/v1/admin/reports/${id}/assign`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd
      });
      if (res.ok) {
        toast("success", `Assigned to ${assignedTo}`);
        fetchQueue();
      }
    } catch {
      toast("error", "Assignment failed");
    }
  };

  const handleOverrideTriage = async (id: string, newSev: string) => {
    try {
      const fd = new FormData();
      fd.append("severity", newSev);
      const res = await fetch(`/api/v1/admin/reports/${id}/triage`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd
      });
      if (res.ok) {
        toast("success", `Severity updated to ${newSev}`);
        fetchQueue();
      }
    } catch {
      toast("error", "Override failed");
    }
  };

  const handleResolveSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resolveTarget || !resolvePhoto) {
      toast("error", "Mandatory resolution proof photo is required.");
      return;
    }
    try {
      setResolving(true);
      const fd = new FormData();
      fd.append("resolution_notes", resolveNotes);
      fd.append("proof_photo", resolvePhoto);
      const res = await fetch(`/api/v1/admin/reports/${resolveTarget.id}/resolve`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd
      });
      if (res.ok) {
        toast("success", "Ticket resolved with verified proof photo!");
        setResolveTarget(null);
        setResolvePhoto(null);
        setResolveNotes("");
        fetchQueue();
      } else {
        const err = await res.json();
        toast("error", err.detail || "Resolution failed");
      }
    } catch {
      toast("error", "Failed to submit resolution");
    } finally {
      setResolving(false);
    }
  };

  const handleAutoFile = async (id: string) => {
    try {
      setAutofilingId(id);
      const res = await fetch(`/api/v1/reports/${id}/autofile`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      if (res.ok) {
        toast("success", `Escalated to CPGRAMS! Ref: ${data.confirmation_number}`);
        fetchQueue();
      } else {
        toast("error", data.detail || "AutoFile escalation failed");
      }
    } catch {
      toast("error", "Failed to trigger AutoFile agent");
    } finally {
      setAutofilingId(null);
    }
  };

  // Metrics
  const p1Count = reports.filter((r) => r.severity === "P1" && r.status !== "RESOLVED").length;
  const breachedCount = reports.filter((r) => r.sla_breached).length;
  const resolvedCount = reports.filter((r) => r.status === "RESOLVED").length;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {/* Top Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-navy-100 pb-6">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full bg-navy-100 px-3 py-1 text-xs font-semibold text-navy-800">
            <Building2 className="size-3.5 text-navy-700" /> Municipal Operations Desk
          </div>
          <h1 className="mt-2 text-3xl font-extrabold text-navy-900">
            Triage & Escalation Dispatch Console
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Official municipal surface for reviewing AI-triaged civic reports, verifying resolution proof, and triggering autonomous state filing.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {isAdmin ? (
            <div className="flex items-center gap-2 rounded-xl bg-emerald-50 px-3.5 py-2 ring-1 ring-emerald-200">
              <UserCheck className="size-4 text-emerald-700" />
              <div className="text-xs">
                <span className="font-semibold text-emerald-900">{adminUser?.name || "Admin"}</span>
                <span className="ml-1 text-emerald-700">(Verified Desk Officer)</span>
              </div>
            </div>
          ) : (
            <Button onClick={loginAsAdmin} variant="primary">
              Sign In as Municipal Admin
            </Button>
          )}
          <Button onClick={() => fetchQueue()} variant="secondary" aria-label="Refresh queue">
            <RefreshCw className="size-4" />
          </Button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-2xl bg-white p-4 ring-1 ring-navy-100 shadow-sm">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Queue Total</div>
          <div className="mt-1 text-2xl font-black text-navy-900">{reports.length}</div>
        </div>
        <div className="rounded-2xl bg-red-50 p-4 ring-1 ring-red-200 shadow-sm">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-red-700 uppercase tracking-wider">
            <AlertTriangle className="size-3.5" /> P1 Emergencies
          </div>
          <div className="mt-1 text-2xl font-black text-red-900">{p1Count}</div>
        </div>
        <div className="rounded-2xl bg-amber-50 p-4 ring-1 ring-amber-200 shadow-sm">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-700 uppercase tracking-wider">
            <Clock className="size-3.5" /> SLA Breached
          </div>
          <div className="mt-1 text-2xl font-black text-amber-900">{breachedCount}</div>
        </div>
        <div className="rounded-2xl bg-emerald-50 p-4 ring-1 ring-emerald-200 shadow-sm">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-700 uppercase tracking-wider">
            <CheckCircle className="size-3.5" /> Resolved with Proof
          </div>
          <div className="mt-1 text-2xl font-black text-emerald-900">{resolvedCount}</div>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-slate-50 p-3 ring-1 ring-navy-100">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold text-slate-500 uppercase px-2">Filters:</span>
          {/* Status */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-navy-900"
          >
            <option value="ALL">All Statuses</option>
            <option value="SUBMITTED">SUBMITTED</option>
            <option value="TRIAGED">TRIAGED</option>
            <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
            <option value="ASSIGNED">ASSIGNED</option>
            <option value="IN_PROGRESS">IN_PROGRESS</option>
            <option value="RESOLVED">RESOLVED</option>
          </select>

          {/* Ward */}
          <select
            value={wardFilter}
            onChange={(e) => setWardFilter(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-navy-900"
          >
            <option value="ALL">All Wards</option>
            <option value="BBMP-111">BBMP-111 (Shantinagar)</option>
            <option value="BBMP-151">BBMP-151 (Koramangala)</option>
            <option value="PMC-12">PMC-12 (Kothrud)</option>
            <option value="MCD-54">MCD-54 (Karol Bagh)</option>
          </select>

          {/* Severity */}
          <select
            value={sevFilter}
            onChange={(e) => setSevFilter(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-navy-900"
          >
            <option value="ALL">All Severities</option>
            <option value="P1">P1 (Critical)</option>
            <option value="P2">P2 (Urgent)</option>
            <option value="P3">P3 (Routine)</option>
          </select>
        </div>

        <div className="text-xs font-semibold text-slate-500">
          Showing {filtered.length} of {reports.length} records
        </div>
      </div>

      {/* Triage Queue List */}
      <div className="mt-6 space-y-4">
        {filtered.map((r) => (
          <motion.div
            key={r.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className={`rounded-2xl border bg-white p-5 shadow-sm transition hover:shadow-md ${
              r.severity === "P1" && r.status !== "RESOLVED"
                ? "border-red-300 ring-2 ring-red-100"
                : r.sla_breached
                ? "border-amber-300 ring-1 ring-amber-100"
                : "border-navy-100"
            }`}
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="flex-1">
                {/* Header Pills */}
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-md border px-2 py-0.5 text-xs font-extrabold ${SEV_BADGE[r.severity]}`}>
                    {r.severity}
                  </span>
                  <span className="rounded-md bg-navy-100 px-2 py-0.5 text-xs font-semibold text-navy-800">
                    {r.ward_name} ({r.ward_id}) · {r.city}
                  </span>
                  <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                    {r.category.toUpperCase()}
                  </span>
                  <span className="rounded-md bg-navy-50 px-2 py-0.5 text-xs font-bold text-navy-700">
                    STATUS: {r.status}
                  </span>
                  {r.sla_breached && (
                    <span className="rounded-md bg-red-600 px-2 py-0.5 text-xs font-bold text-white">
                      ⚠️ SLA BREACHED
                    </span>
                  )}
                  {r.duplicate_of && (
                    <span className="rounded-md bg-purple-100 text-purple-800 border border-purple-200 px-2 py-0.5 text-xs font-semibold">
                      Deduplicated (Merged)
                    </span>
                  )}
                  {r.upvotes > 1 && (
                    <span className="inline-flex items-center gap-1 rounded-md bg-blue-50 text-blue-700 px-2 py-0.5 text-xs font-bold">
                      <ThumbsUp className="size-3" /> {r.upvotes}
                    </span>
                  )}
                </div>

                {/* Description */}
                <h3 className="mt-2.5 text-base font-bold text-navy-900">{r.description}</h3>

                {/* Metadata & POI proximity */}
                <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-slate-500">
                  <span className="flex items-center gap-1">
                    <MapPin className="size-3.5 text-slate-400" />
                    {r.latitude.toFixed(4)}, {r.longitude.toFixed(4)}
                  </span>
                  {r.poi_multiplier > 1.0 && (
                    <span className="font-semibold text-amber-700">
                      ⚡ Infrastructure Multiplier: {r.poi_multiplier}x
                    </span>
                  )}
                  {r.assigned_to && (
                    <span className="font-semibold text-navy-800">
                      Assigned: {r.assigned_to}
                    </span>
                  )}
                  {r.sla_deadline && (
                    <span>
                      Deadline: {new Date(r.sla_deadline).toLocaleString()}
                    </span>
                  )}
                </div>

                {/* Resolution proof link if resolved */}
                {r.resolution_proof_url && (
                  <div className="mt-3 flex items-center gap-2 rounded-xl bg-emerald-50 p-2.5 text-xs text-emerald-900 border border-emerald-200">
                    <FileCheck className="size-4 text-emerald-700" />
                    <span><strong>Proof Verified:</strong> Hot-mix bitumen patch completed.</span>
                    <a
                      href={r.resolution_proof_url}
                      target="_blank"
                      rel="noreferrer"
                      className="ml-auto inline-flex items-center gap-1 font-semibold text-emerald-800 underline hover:text-emerald-950"
                    >
                      <Eye className="size-3.5" /> View Photo Proof
                    </a>
                  </div>
                )}
              </div>

              {/* Action Buttons Column */}
              <div className="flex flex-col sm:flex-row flex-wrap items-center gap-2">
                {/* Accept / Override Severity */}
                <div className="flex items-center rounded-lg border border-slate-200 bg-slate-50 p-1">
                  <span className="px-1.5 text-[10px] font-bold text-slate-500">SEV:</span>
                  {(["P1", "P2", "P3"] as const).map((s) => (
                    <button
                      key={s}
                      onClick={() => handleOverrideTriage(r.id, s)}
                      className={`rounded px-1.5 py-0.5 text-[11px] font-bold ${
                        r.severity === s ? "bg-white text-navy-900 shadow-xs" : "text-slate-500 hover:text-navy-900"
                      }`}
                    >
                      {s}
                    </button>
                  ))}
                </div>

                {/* Acknowledge */}
                {r.status === "TRIAGED" && (
                  <Button size="sm" variant="secondary" onClick={() => handleAcknowledge(r.id)}>
                    Acknowledge
                  </Button>
                )}

                {/* Quick Assign */}
                {["TRIAGED", "ACKNOWLEDGED"].includes(r.status) && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      const div = r.category === "water" ? "BWSSB Emergency" : r.category === "roads_potholes" ? "Road Paving Division" : "Sanitation Quick Response";
                      handleAssign(r.id, div);
                    }}
                  >
                    Assign to Division
                  </Button>
                )}

                {/* Resolve with Proof Photo */}
                {r.status !== "RESOLVED" && (
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => setResolveTarget(r)}
                  >
                    <CheckCircle className="size-3.5 mr-1" /> Resolve
                  </Button>
                )}

                {/* AutoFile Escalation Agent */}
                {(r.severity === "P1" || r.sla_breached) && (
                  <Button
                    size="sm"
                    variant="danger"
                    disabled={autofilingId === r.id}
                    onClick={() => handleAutoFile(r.id)}
                  >
                    <Send className="size-3.5 mr-1" />
                    {autofilingId === r.id ? "Escalating..." : "AutoFile CPGRAMS"}
                  </Button>
                )}
              </div>
            </div>
          </motion.div>
        ))}

        {filtered.length === 0 && (
          <div className="py-12 text-center text-slate-500">
            No civic tickets match the selected filters.
          </div>
        )}
      </div>

      {/* RESOLVE WITH MANDATORY PROOF PHOTO MODAL */}
      <AnimatePresence>
        {resolveTarget && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl ring-1 ring-navy-100"
            >
              <div className="flex items-center justify-between border-b border-navy-100 pb-4">
                <div className="flex items-center gap-2">
                  <FileCheck className="size-5 text-emerald-600" />
                  <h2 className="text-lg font-bold text-navy-900">Resolve Ticket with Proof</h2>
                </div>
                <button
                  onClick={() => setResolveTarget(null)}
                  className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                >
                  <XCircle className="size-5" />
                </button>
              </div>

              <form onSubmit={handleResolveSubmit} className="mt-4 space-y-4">
                <div className="rounded-xl bg-slate-50 p-3 text-xs text-slate-600">
                  <strong>Ticket #{resolveTarget.id.slice(0, 8)}:</strong> {resolveTarget.description}
                </div>

                <div>
                  <label className="block text-xs font-bold text-navy-900 uppercase">
                    Mandatory Resolution Proof Photo <span className="text-red-500">*</span>
                  </label>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Upload inspection photo proving repair completion. Prevents fraudulent closure.
                  </p>
                  <input
                    type="file"
                    accept="image/jpeg,image/png"
                    required
                    onChange={(e) => setResolvePhoto(e.target.files?.[0] || null)}
                    className="mt-2 block w-full text-xs text-slate-600 file:mr-3 file:rounded-xl file:border-0 file:bg-navy-50 file:px-4 file:py-2.5 file:text-xs file:font-semibold file:text-navy-700 hover:file:bg-navy-100"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-navy-900 uppercase">
                    Work Completion Notes <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    required
                    rows={3}
                    value={resolveNotes}
                    onChange={(e) => setResolveNotes(e.target.value)}
                    placeholder="e.g. Hot-mix bitumen applied, water line clamped and leak tested by Rapid Response Team."
                    className="mt-1.5 w-full rounded-xl border border-navy-100 p-3 text-sm outline-none focus:border-navy-400 focus:ring-2 focus:ring-navy-100"
                  />
                </div>

                <div className="mt-6 flex items-center justify-end gap-3">
                  <Button type="button" variant="secondary" onClick={() => setResolveTarget(null)}>
                    Cancel
                  </Button>
                  <Button type="submit" variant="primary" disabled={resolving || !resolvePhoto}>
                    {resolving ? "Verifying..." : "Confirm Resolution"}
                  </Button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
