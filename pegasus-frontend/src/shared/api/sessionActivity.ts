/** Tracks last meaningful API activity for inactivity-based session prompts. */

const EXCLUDED_URL_PARTS = [
  '/admin/auth/session',
  '/admin/auth/me',
  '/admin/auth/extend',
  '/admin/auth/logout',
  '/admin/auth/login',
  '/admin/auth/signup',
];
const EXTEND_THROTTLE_MS = 10 * 60 * 1000;

let lastActivityMs = Date.now();
let lastExtendAttemptMs = 0;
let extendSessionFn: (() => Promise<void>) | null = null;

export function registerSessionExtender(fn: (() => Promise<void>) | null): void {
  extendSessionFn = fn;
}

export function recordSessionActivity(url: string): void {
  if (EXCLUDED_URL_PARTS.some((part) => url.includes(part))) return;
  lastActivityMs = Date.now();

  const now = Date.now();
  if (extendSessionFn && now - lastExtendAttemptMs >= EXTEND_THROTTLE_MS) {
    lastExtendAttemptMs = now;
    void extendSessionFn().catch(() => {});
  }
}

export function getLastSessionActivityMs(): number {
  return lastActivityMs;
}

export function resetSessionActivity(): void {
  lastActivityMs = Date.now();
  lastExtendAttemptMs = 0;
}
