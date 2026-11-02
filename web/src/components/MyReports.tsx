import { BadgeCheck, CircleAlert, Image, Languages, ThumbsDown, ThumbsUp } from "lucide-react";
import { useEffect, useState } from "react";
import { ago, myReports, type MyReport } from "../api";
import { getAuthSession } from "../auth";
import { Badge, Button, Card, useToast } from "./ui";

type Tone = "navy" | "saffron" | "leaf" | "gray" | "red" | "blue";
const STATUS: Record<string, { label: string; tone: Tone }> = {
  SUBMITTED: { label: "Received", tone: "gray" }, TRIAGED: { label: "Received", tone: "gray" },
  ACKNOWLEDGED: { label: "Seen by the desk", tone: "blue" }, ASSIGNED: { label: "Work assigned", tone: "navy" },
  IN_PROGRESS: { label: "Being fixed", tone: "saffron" }, RESOLVED: { label: "Marked fixed", tone: "leaf" },
  REJECTED: { label: "Closed, not actionable", tone: "red" },
};

/** The signed-in citizen's reports. A repair counts as confirmed only when the person who reported it says so. */
export function MyReports({ refreshKey = 0 }: { refreshKey?: number }) {
  const session = getAuthSession();
  const toast = useToast();
  const [items, setItems] = useState<MyReport[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [disputing, setDisputing] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const citizen = session?.user.role === "citizen";

  const load = () => myReports.list().then(setItems).catch(() => setItems([]));
  useEffect(() => { if (citizen) load(); }, [citizen, refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (id: string, run: () => Promise<unknown>, done: string) => {
    setBusy(id);
    try { await run(); toast("ok", done); setDisputing(null); setReason(""); await load(); }
    catch (e) { toast("error", (e as Error).message); }
    setBusy(null);
  };

  if (!citizen || !items?.length) return null;
  const waiting = items.filter((r) => r.awaiting_your_check).length;
  return (
    <section className="mx-auto max-w-7xl px-4 pt-4" aria-labelledby="mine">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <h2 id="mine" className="text-2xl font-extrabold text-navy-900">Your reports</h2>
        {waiting > 0 && <Badge tone="saffron">{waiting} waiting for your check</Badge>}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {items.slice(0, 6).map((r) => {
          const st = STATUS[r.status] ?? { label: r.status, tone: "gray" as Tone };
          return (
            <Card key={r.id} variant="plain" className={`min-w-0 p-4 ${r.awaiting_your_check ? "ring-2 ring-saffron-300" : ""}`}>
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={st.tone}>{st.label}</Badge>
                <span className="text-sm font-semibold text-navy-900">{r.category.replace(/_/g, " ")}</span>
                {r.language && r.language !== "English" && <span className="inline-flex items-center gap-1 text-xs text-slate-500"><Languages className="size-3.5" />{r.language}</span>}
                <span className="ml-auto font-mono text-xs text-slate-500" title={r.id}>#{r.id.slice(0, 8)}</span>
              </div>
              <p className="mt-2 line-clamp-2 break-words text-sm text-slate-700">{r.description}</p>
              <p className="mt-1 text-xs text-slate-500">{[r.ward, r.city].filter(Boolean).join(", ")} · reported {ago(r.created_at)}</p>

              {r.resolution_notes && <p className="mt-3 rounded-xl bg-leaf-50 p-2.5 text-sm text-leaf-900"><b>Municipality:</b> {r.resolution_notes}</p>}
              {r.resolution_proof_url && (
                <a href={r.resolution_proof_url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex items-center gap-1.5 text-sm font-semibold text-navy-700 hover:underline">
                  <Image className="size-4" />See their proof photo
                </a>
              )}

              {r.citizen_verdict === "confirmed" && <p className="mt-3 flex items-center gap-1.5 text-sm font-bold text-leaf-700"><BadgeCheck className="size-4" />You confirmed it is fixed</p>}
              {r.citizen_verdict === "disputed" && <p className="mt-3 flex items-center gap-1.5 text-sm font-bold text-red-700"><CircleAlert className="size-4" />You said it is not fixed, so it was reopened at higher priority</p>}

              {r.awaiting_your_check && (
                <div className="mt-3 rounded-xl bg-saffron-50 p-3 ring-1 ring-saffron-200">
                  <p className="text-sm font-semibold text-navy-900">The municipality says this is fixed. Is it?</p>
                  {disputing === r.id ? (
                    <div className="mt-2 space-y-2">
                      <label htmlFor={`why-${r.id}`} className="text-xs font-semibold text-navy-900">What is still wrong? (any language)</label>
                      <textarea id={`why-${r.id}`} className="w-full rounded-xl border border-navy-100 bg-white p-2.5 text-sm outline-none focus:border-navy-400 focus:ring-4 focus:ring-navy-100" rows={2} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. The pothole was filled with loose gravel and is open again." />
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" variant="danger" loading={busy === r.id} onClick={() => act(r.id, () => myReports.dispute(r.id, reason), "Reopened. The desk will see it again within 24 hours.")}>Reopen my report</Button>
                        <Button size="sm" variant="ghost" onClick={() => setDisputing(null)}>Cancel</Button>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Button size="sm" variant="primary" loading={busy === r.id} onClick={() => act(r.id, () => myReports.confirm(r.id), "Thank you. The board now shows the repair as confirmed by you.")}><ThumbsUp className="size-4" />Yes, it is fixed</Button>
                      <Button size="sm" variant="secondary" onClick={() => setDisputing(r.id)}><ThumbsDown className="size-4" />No, still a problem</Button>
                    </div>
                  )}
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </section>
  );
}
