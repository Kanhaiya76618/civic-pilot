export type CivicRole = "citizen" | "admin";

export type AuthSession = {
  token: string;
  user: { id: string; email: string; name: string; role: CivicRole };
};

const KEY = "civic-pulse-auth";
const EVENT = "civic-pulse-auth-change";

export function getAuthSession(): AuthSession | null {
  try {
    const value = sessionStorage.getItem(KEY);
    if (!value) return null;
    const parsed = JSON.parse(value) as AuthSession;
    return parsed.token && parsed.user?.role ? parsed : null;
  } catch {
    return null;
  }
}

export function setAuthSession(session: AuthSession) {
  sessionStorage.setItem(KEY, JSON.stringify(session));
  window.dispatchEvent(new Event(EVENT));
}

export function clearAuthSession() {
  sessionStorage.removeItem(KEY);
  window.dispatchEvent(new Event(EVENT));
}

export const authChangeEvent = EVENT;
