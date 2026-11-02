// One client for everything the UI talks to. Part 3 is this server; Part 1 and Part 2 are reached
// through server-side proxies (/app/part1, /app/part2) configured with PART1_API_URL / PART2_API_URL.

export type InputDef = {
  key: string; source: "input" | "vault"; required: boolean; free_text: boolean; max_len: number;
  pattern: string | null; enum: string[] | null; label: string | null; verify: "ifsc" | "pincode" | null;
};
export type DocDef = { key: string; required: boolean; max_kb: number; formats: string[]; label: string | null };
export type Service = {
  portal_id: string; portal_name: string; service_id: string; description: string; status: string;
  is_sandbox: boolean; submission_enabled: boolean; public_demo: boolean; read_only: boolean;
  explorable: boolean; has_recorded_route: boolean; inputs: InputDef[]; documents: DocDef[];
  derive?: Record<string, Record<string, Record<string, string>>>;
};
export type Timing = {
  agent_ms?: number; browser_ms?: number; model_ms?: number; human_wait_ms?: number; total_ms?: number;
  model_calls?: number; input_tokens?: number; output_tokens?: number;
};
export type Run = {
  service: string; portal_id: string; service_id: string; strategy: string; status: string; outcome: string | null;
  results: number | null; timing: Timing; created_at: string; category: string | null; district: string | null;
  location: [number, number] | null; reference_no: string | null;
};
export type TaskEvent = {
  seq: number; kind: string; status: string; message: string; step_id: string | null; at: string;
  data: { do?: string; label?: string; value?: string; host?: string; kind?: string; turn?: number; status?: string;
          model_ms?: number; actions?: { action: string; ref: string; value_key: string }[]; result?: Result };
};
export type Result = { source_url: string; retrieved_at: string; count?: number | null; items: { title: string; url: string | null }[] };
export type Receipt = {
  receipt_id: string; task_id: string; portal_id: string; service_id: string; mode: string;
  outcome: "submitted" | "dry_run_complete" | "information_retrieved"; reference_no: string | null; submitted_at: string;
  approved_by: string | null; evidence: { name: string; sha256: string }[]; tracking: Record<string, string>;
  result: Result | null; timing: Timing; signer_key_id: string; signature: string;
};
export type ApprovalCard = {
  portal: { name: string; is_sandbox: boolean }; service: string; mode: string;
  values: { label: string; value: string; source: string; readback_ok: boolean }[];
  documents: { key: string; size_kb: number; note: string }[]; agent_extra_actions: string[];
  differences: string[]; warnings: string[]; next: string;
};
export type TaskState = {
  task_id: string; status: string; error: string | null; mode: string; strategy: string; created_at: string;
  portal: { id: string; name: string; is_sandbox: boolean }; service: string;
  human: { kind: string; instructions: string } | null; approval_pending: boolean; card: ApprovalCard | null;
  timing: Timing; receipt: Receipt | null; page_url: string | null; has_final: boolean; events: TaskEvent[];
};
export type AppConfig = { part1_connected: boolean; part2_connected: boolean; ai_available: boolean; judge_demo?: boolean; officer_signup?: boolean };
export type Lookup = { ok: boolean | null; source: string; data: Record<string, any>; error: string | null };

export const TERMINAL = new Set(["completed", "failed", "needs_review"]);

// ------------------------------------------------------------------ agent console (free-form runs)
export type StepAction = { name: string; ref?: string; text?: string; url?: string; press_enter?: boolean; answer?: string; label?: string | null; value?: string | null };
export type RunStep = {
  step_no: number; kind: string; title: string; screenshot: boolean; at: string; t_ms: number; url: string | null;
  previous_goal?: string; eval?: string; memory?: string; next_goal?: string; action?: StepAction; outcome?: string;
  ai_calls?: number; duration_ms?: number; results?: { title: string; url: string; snippet: string }[];
  extracted?: string[]; note?: string; plan?: Record<string, unknown>; reason?: string; allowed?: string[]; detail?: string;
};
export type RunItem = { name: string; url: string; summary: string; eligibility: string; benefits: string; location: string; source: string; verified: boolean };
export type RunResult = { query: string; answer: string; items: RunItem[]; sources: string[]; retrieved_at: string; dropped_unverified: number };
export type RunStats = { ai_calls: number; model_ms: number; wall_ms: number; steps: number; cache_hit: boolean; replay_ms?: number; search_provider: string | null; input_tokens?: number; output_tokens?: number };
export type AgentRun = {
  run_id: string; query: string; title: string | null; intent: string | null; strategy: string | null; status: string;
  task_id: string | null; task_status?: string | null; result: RunResult | null; stats: RunStats; error: string | null;
  extra: { offer?: { portal_id: string; service_id: string; prefill: Record<string, string>; missing: string[] };
           handoff?: { portal_id: string; service_id: string; prefill: Record<string, string>; districts?: string[] }; private?: boolean } | null;
  created_at: string; updated_at: string;
};
export const RUN_TERMINAL = new Set(["completed", "failed", "stopped", "out_of_scope", "handed_off", "needs_details", "needs_review"]);

const tq = (t?: string | null) => (t ? `?t=${encodeURIComponent(t)}` : "");
const post = (url: string, body?: object) =>
  fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined }).then(json<{ ok: boolean }>);

export const agent = {
  start: (query: string) =>
    fetch("/app/agent/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query }) })
      .then(json<{ run_id: string; token: string; path: string }>),
  runs: (limit = 50) => fetch(`/app/agent/runs?limit=${limit}`).then(json<AgentRun[]>),
  run: (id: string) => fetch(`/app/agent/runs/${id}`).then(json<{ run: AgentRun; steps: RunStep[] }>),
  eventsUrl: (id: string, after: number) => `/app/agent/runs/${id}/events?after=${after}`,
  shot: (id: string, n: number, t?: string | null) => `/app/agent/runs/${id}/steps/${n}.jpg${tq(t)}`,
  approve: (id: string, t: string, decision: "approved" | "rejected") => post(`/app/agent/runs/${id}/approve${tq(t)}`, { decision }),
  humanDone: (id: string, t: string) => post(`/app/agent/runs/${id}/human/done${tq(t)}`),
  cancel: (id: string, t: string) => post(`/app/agent/runs/${id}/cancel${tq(t)}`),
  room: (id: string, t: string) => fetch(`/app/agent/runs/${id}/room${tq(t)}`).then(json<{ path: string }>),
  link: (id: string, t: string, task_id: string) => post(`/app/agent/runs/${id}/link${tq(t)}`, { task_id }),
};

/** Control tokens for runs started in this browser (view-only without one). */
export const runTokens = {
  get(id: string): string | null {
    try { return JSON.parse(sessionStorage.getItem("cp-run-tokens") ?? "{}")[id] ?? null; } catch { return null; }
  },
  set(id: string, token: string) {
    try {
      const all = JSON.parse(sessionStorage.getItem("cp-run-tokens") ?? "{}");
      sessionStorage.setItem("cp-run-tokens", JSON.stringify({ ...all, [id]: token }));
    } catch { /* private mode: control works from the link only */ }
  },
};

async function json<T>(r: Response): Promise<T> {
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof body.detail === "string" ? body.detail : `Request failed (${r.status})`);
  return body as T;
}

export const api = {
  config: () => fetch("/app/config").then(json<AppConfig>),
  services: () => fetch("/app/services").then(json<Service[]>),
  runs: () => fetch("/app/runs").then(json<Run[]>),
  pincode: (pin: string) => fetch(`/app/lookup/pincode/${encodeURIComponent(pin)}`).then(json<Lookup>),
  ifsc: (code: string) => fetch(`/app/lookup/ifsc/${encodeURIComponent(code)}`).then(json<Lookup>),
  start: (payload: object, files: { key: string; file: File }[]) => {
    const fd = new FormData();
    fd.append("payload", JSON.stringify(payload));
    files.forEach(({ key, file }) => fd.append("files", file, `${key}::${file.name}`));
    return fetch("/app/start", { method: "POST", body: fd }).then(json<{ task_id: string; citizen_path: string }>);
  },
  task: (taskId: string, token: string) => fetch(`/citizen/${taskId}/state?t=${encodeURIComponent(token)}`).then(json<TaskState>),
  approve: (taskId: string, token: string, decision: "approved" | "rejected") =>
    fetch(`/citizen/${taskId}/approve?t=${encodeURIComponent(token)}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision }),
    }).then(json),
  humanDone: (taskId: string, token: string) => fetch(`/citizen/${taskId}/human/done?t=${encodeURIComponent(token)}`, { method: "POST" }).then(json),
  humanCancel: (taskId: string, token: string) => fetch(`/citizen/${taskId}/human/cancel?t=${encodeURIComponent(token)}`, { method: "POST" }).then(json),
  verify: (receipt: Receipt) =>
    fetch("/v1/receipts/verify", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(receipt) })
      .then(json<{ valid: boolean; meaning: string }>),
  sandboxSms: () => fetch("/app/sandbox/sms").then(json<{ messages: { to: string; text: string; at: number }[] }>),
  liveUrl: (taskId: string, token: string) =>
    `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/citizen/${taskId}/live?t=${encodeURIComponent(token)}`,
  part1: (path: string, init?: RequestInit) => fetch(`/app/part1/${path}`, authenticatedInit(init)).then(json<any>),
  part2: (path: string, init?: RequestInit) => fetch(`/app/part2/${path}`, authenticatedInit(init)).then(json<any>),
};

export const secs = (ms?: number | null) => (ms == null ? "–" : ms < 10_000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms / 1000)}s`);

// ------------------------------------------------------------------ home page: live news and the citizen's own history
export type NewsItem = { title: string; url: string; source: string; published: string | null; topic: string; official: boolean; lang: string };
export type News = { updated_at: string; items: NewsItem[]; trending: { term: string; count: number }[]; topics: { id: string; label: string }[];
  sources: string[]; stale: boolean };
export type HistoryKind = "explain" | "agent" | "lookup" | "filing" | "report" | "news";
export type HistoryEntry = { id: string; kind: HistoryKind; title: string; subtitle: string | null; link: string | null; meta: Record<string, unknown>; created_at: string };
export type CivicGuideSource = { title: string; url: string; excerpt: string };
export type CivicGuideAnswer = {
  answer: string; category: string; disclaimer: string; sources: CivicGuideSource[];
  retrieval_status: "grounded_in_official_sources" | "no_official_sources" | "portal_guide";
  mode: "civic" | "portal";
  actions: { label: string; path: string }[];
  support: { email?: string | null; phone?: string | null; url?: string | null } | null;
};

function authHeaders(): Record<string, string> {
  try {
    const raw = sessionStorage.getItem("civic-pulse-auth");
    const token = raw ? (JSON.parse(raw).token as string) : "";
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch { return {}; }
}

/** Preserve multipart headers while adding the signed-in user's application token. */
function authenticatedInit(init?: RequestInit): RequestInit {
  const headers = new Headers(init?.headers);
  for (const [name, value] of Object.entries(authHeaders())) headers.set(name, value);
  return { ...init, headers };
}

export const me = {
  news: (refresh = false) => fetch(`/app/news${refresh ? "?refresh=true" : ""}`).then(json<News>),
  history: (kind?: HistoryKind) => fetch(`/app/me/history${kind ? `?kind=${kind}` : ""}`, { headers: authHeaders() }).then(json<HistoryEntry[]>),
  add: (entry: { kind: HistoryKind; title: string; subtitle?: string | null; link?: string | null; meta?: Record<string, unknown> }) =>
    fetch("/app/me/history", { method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() }, body: JSON.stringify(entry) })
      .then(json<HistoryEntry & { already_saved?: boolean }>),
  remove: (id: string) => fetch(`/app/me/history/${id}`, { method: "DELETE", headers: authHeaders() }).then(json<{ ok: boolean }>),
  clear: (kind?: HistoryKind) => fetch(`/app/me/history${kind ? `?kind=${kind}` : ""}`, { method: "DELETE", headers: authHeaders() }).then(json<{ deleted: number }>),
};

/** The civic guide is authenticated and uses a server-only Groq key. */
export const civicGuide = {
  ask: (message: string, language = "English", scope: "auto" | "civic" | "portal" = "auto") =>
    fetch("/api/v1/civic-guide/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ message, language, scope }),
    }).then(json<CivicGuideAnswer>),
};

/** Part 2: the signed-in citizen's own reports, and their word on a repair. */
export type MyReport = {
  id: string; category: string; description: string; status: string; severity: string; ward: string | null; city: string;
  created_at: string | null; sla_deadline: string | null; resolution_notes: string | null; resolution_proof_url: string | null;
  citizen_verdict: "confirmed" | "disputed" | null; awaiting_your_check: boolean; language: string | null; ticket: string; department: string;
};
export const myReports = {
  list: () => fetch("/api/v1/me/reports", { headers: authHeaders() }).then(json<MyReport[]>),
  confirm: (id: string) => fetch(`/api/v1/reports/${id}/confirm`, { method: "POST", headers: authHeaders() }).then(json<{ ok: boolean }>),
  dispute: (id: string, reason: string) => {
    const fd = new FormData();
    fd.append("reason", reason);
    return fetch(`/api/v1/reports/${id}/dispute`, { method: "POST", headers: authHeaders(), body: fd }).then(json<{ ok: boolean; message: string }>);
  },
};

/** Part 2 intake: what the checks see before filing (nothing saved), the voice note as text, and the ticket. */
export type ReportPreview = {
  perception: { pothole_detected?: boolean; pothole_count?: number; method?: string | null; is_blurry?: boolean };
  findings: string[]; findings_local?: string[]; reasons?: string[]; reasons_local?: string[];
  annotated_photo: string | null; department: string; severity?: string; severity_name?: string; sla_hours?: number;
  ward_name?: string; ward_id?: string; city?: string; nearest_poi?: string | null; nearest_poi_distance_m?: number | null;
  nearby_report?: { ticket: string; status: string; distance_m: number } | null;
};
export type FiledReport = {
  ticket: string; id: string; department: string; severity: string; severity_name: string; sla_hours: number; sla_deadline: string | null;
  ward_name: string; city: string; reasons: string[]; findings: string[]; translating: boolean; duplicate_of: string | null;
};
export type Heard = { text: string; language: string | null; language_name: string | null };
export const reportApi = {
  transcribe: (audio: Blob) => {
    const fd = new FormData();
    fd.append("audio", audio, `voice-note.${audio.type.includes("ogg") ? "ogg" : audio.type.includes("mp4") ? "m4a" : "webm"}`);
    return fetch("/api/v1/reports/transcribe", { method: "POST", headers: authHeaders(), body: fd }).then(json<Heard>);
  },
  preview: (fd: FormData) => fetch("/api/v1/reports/preview", { method: "POST", headers: authHeaders(), body: fd }).then(json<ReportPreview>),
  file: (fd: FormData) => fetch("/api/v1/reports", { method: "POST", headers: authHeaders(), body: fd }).then(json<FiledReport>),
};

/** Keep a line in the signed-in citizen's history. Never blocks or breaks the action that triggered it. */
export function remember(entry: Parameters<typeof me.add>[0]) {
  if (!authHeaders().Authorization) return;
  me.add(entry).catch(() => {});
}

export function ago(iso: string | null): string {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 90) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  if (s < 86400 * 7) return `${Math.round(s / 86400)} d ago`;
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}
