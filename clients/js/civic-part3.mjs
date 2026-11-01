// Tiny client for Swayam-sevak Part 3 (Node 18+ or the browser; copy this one file).
//
//   import { Part3 } from "./civic-part3.mjs";
//   const p3 = new Part3("http://<host>:8000", process.env.CIVIC_API_KEY);
//   const task = await p3.start({ portalId: "sandbox", serviceId: "public_grievance", citizenId: "cit_1",
//                                 inputs: {...}, private: { mobile: "..." }, mode: "assist", originRef: "issue-42" });
//   // send task.citizen_url to the citizen (OTP, CAPTCHA, approval)
//   const done = await p3.wait(task.task_id);
//   // webhook handler (Node): Part3.verifyWebhook(rawBodyString, req.headers, secret)

export class Part3 {
  constructor(baseUrl, apiKey = "") {
    this.base = baseUrl.replace(/\/$/, "");
    this.headers = apiKey ? { "X-API-Key": apiKey } : {};
  }

  async #json(path, init = {}) {
    const r = await fetch(this.base + path, { ...init, headers: { ...this.headers, ...(init.headers || {}) } });
    const body = await r.json();
    if (!r.ok) throw new Error(body.detail ? JSON.stringify(body.detail) : `HTTP ${r.status}`);
    return body;
  }

  #post(path, data) {
    return this.#json(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
  }

  services() { return this.#json("/v1/registry"); }
  task(taskId) { return this.#json(`/v1/tasks/${taskId}`); }

  async start({ portalId, serviceId, citizenId, inputs, private: priv, mode = "dry_run", origin = "part2", originRef, callbackUrl }) {
    const consentId = "cons_" + crypto.randomUUID().slice(0, 12);
    await this.#post("/v1/consents", {
      consent_id: consentId, citizen_id: citizenId, portal_ids: [portalId], service_ids: [serviceId],
      purpose: `${serviceId} with approval before submit`, expires_at: new Date(Date.now() + 864e5).toISOString(),
    });
    const vaultRef = priv ? (await this.#post("/v1/vault", { fields: priv })).vault_ref : null;
    return this.#post("/v1/tasks", {
      idempotency_key: `${origin}-${originRef || crypto.randomUUID()}`, citizen_id: citizenId, portal_id: portalId,
      service_id: serviceId, inputs, vault_ref: vaultRef, consent_id: consentId, mode, origin, origin_ref: originRef,
      callback_url: callbackUrl,
    });
  }

  async wait(taskId, timeoutMs = 120000) {
    const end = Date.now() + timeoutMs;
    for (;;) {
      const t = await this.task(taskId);
      if (["completed", "failed", "needs_review"].includes(t.status) || Date.now() > end) return t;
      await new Promise((r) => setTimeout(r, 1000));
    }
  }

  async findSchemes(answers) {
    const t = await this.start({ portalId: "myscheme", serviceId: "find_schemes", citizenId: "cit_" + crypto.randomUUID().slice(0, 8),
                                 inputs: answers, mode: "assist", origin: "part1" });
    return this.wait(t.task_id);
  }

  // Node only: verify X-CivicPulse-Signature on a webhook (pass the raw request body string).
  static async verifyWebhook(rawBody, headers, secret, maxAgeS = 300) {
    const { createHmac, timingSafeEqual } = await import("node:crypto");
    const ts = headers["x-civicpulse-timestamp"], sig = headers["x-civicpulse-signature"] || "";
    if (Math.abs(Date.now() / 1000 - Number(ts)) > maxAgeS) return false;
    const mac = "sha256=" + createHmac("sha256", secret).update(`${ts}.${rawBody}`).digest("hex");
    return mac.length === sig.length && timingSafeEqual(Buffer.from(mac), Buffer.from(sig));
  }
}
