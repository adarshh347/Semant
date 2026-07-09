/**
 * The audience's opaque subject id (Darshan Track F).
 *
 * A session id and nothing else — no name, no email, no handle. It is generated in the
 * browser, kept in localStorage, and sent as `X-Taste-Subject`. The backend rejects any
 * id that could carry identity, so this file cannot become a tracking key by accident.
 *
 * Anonymous session taste works out of the box; an account is what makes the portfolio
 * persist across devices (F3 — identity is the upsell, not the toll).
 */

const KEY = 'darshan.taste.subject';

const randomId = () => {
    // Dashes are allowed by the backend's opaque-id charset; nothing else about a UUID
    // carries meaning, which is the point.
    if (globalThis.crypto?.randomUUID) return `s-${globalThis.crypto.randomUUID()}`;
    const bytes = new Uint8Array(16);
    globalThis.crypto.getRandomValues(bytes);
    return `s-${[...bytes].map(b => b.toString(16).padStart(2, '0')).join('')}`;
};

export function getSubject() {
    let subject = localStorage.getItem(KEY);
    if (!subject) {
        subject = randomId();
        localStorage.setItem(KEY, subject);
    }
    return subject;
}

/** Forget this browser's taste identity entirely (after "clear my taste"). */
export function forgetSubject() {
    localStorage.removeItem(KEY);
}

export const tasteHeaders = () => ({
    'Content-Type': 'application/json',
    'X-Taste-Subject': getSubject(),
});
