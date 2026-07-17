/**
 * Soft Field painting (Differential v1 · increment B).
 *
 * The one Ground type that lives on canvas, not SVG: brush strokes stamped as
 * radial-gradient passes into an alpha buffer (destination-out for subtract),
 * then tinted with the single --accent and drawn at low alpha. No rainbow, no
 * glow — a wash of attention, capped by the opacity discipline (≤0.35).
 *
 * Everything here is pure drawing against the shared stage-geometry contract:
 * stroke points are normalized (0..1, natural-image space); `content` is the
 * letterboxed content box in CSS pixels. Bloom recall = the same painter with
 * `progress` ramping radius and alpha from 0→1.
 */

const WASH_ALPHA = 0.32;          // ≤ the 0.35 wash ceiling
const STAMP_SPACING = 0.35;       // stamps every radius×this along a stroke

export function readAccent() {
    const v = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
    return v || '#5E2B50';
}

// Stamp one stroke into an alpha buffer. Pressure scales the stamp radius so a
// light touch feathers; mice report pressure 0 → treated as a full stamp.
function stampStroke(bctx, stroke, content, dpr, progress) {
    const pts = stroke.points || [];
    if (!pts.length) return;
    const baseR = Math.max(2, (stroke.radius || 0.04) * content.w * dpr) * (0.6 + 0.4 * progress);
    const strength = Math.min(1, (stroke.strength ?? 0.8)) * progress;
    bctx.globalCompositeOperation = stroke.op === 'sub' ? 'destination-out' : 'source-over';

    const stamp = (x, y, pressure) => {
        const r = baseR * (0.55 + 0.45 * (pressure || 1));
        const g = bctx.createRadialGradient(x, y, 0, x, y, r);
        g.addColorStop(0, `rgba(255,255,255,${stroke.op === 'sub' ? 1 : strength})`);
        g.addColorStop(1, 'rgba(255,255,255,0)');
        bctx.fillStyle = g;
        bctx.beginPath();
        bctx.arc(x, y, r, 0, Math.PI * 2);
        bctx.fill();
    };

    const toPx = (p) => {
        const [nx, ny, pr] = Array.isArray(p) ? p : [p.x, p.y, p.p];
        return { x: nx * content.w * dpr, y: ny * content.h * dpr, pr: pr || 0 };
    };

    let prev = toPx(pts[0]);
    stamp(prev.x, prev.y, prev.pr || 1);
    const spacing = baseR * STAMP_SPACING;
    for (let i = 1; i < pts.length; i++) {
        const cur = toPx(pts[i]);
        const dx = cur.x - prev.x, dy = cur.y - prev.y;
        const dist = Math.hypot(dx, dy);
        for (let d = spacing; d <= dist; d += spacing) {
            const t = d / dist;
            stamp(prev.x + dx * t, prev.y + dy * t, (prev.pr || 1) * (1 - t) + (cur.pr || 1) * t);
        }
        prev = cur;
    }
}

/**
 * Paint field Grounds onto `canvas`, sized to the content box.
 * `fields`: [{ ground, alpha?: 0..1, progress?: 0..1 }] — alpha dims unfocused
 * grounds; progress drives bloom recall. Returns quietly if geometry isn't ready.
 */
export function paintFields(canvas, fields, content, { color = null } = {}) {
    if (!canvas || !content || !content.w || !content.h) return;
    const dpr = window.devicePixelRatio || 1;
    const W = Math.round(content.w * dpr);
    const H = Math.round(content.h * dpr);
    if (canvas.width !== W) canvas.width = W;
    if (canvas.height !== H) canvas.height = H;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, W, H);
    if (!fields.length) return;

    const accent = color || readAccent();
    const buffer = document.createElement('canvas');
    buffer.width = W; buffer.height = H;
    const bctx = buffer.getContext('2d');

    for (const { ground, alpha = 1, progress = 1 } of fields) {
        if (!ground?.strokes?.length || progress <= 0 || alpha <= 0) continue;
        bctx.clearRect(0, 0, W, H);
        bctx.globalCompositeOperation = 'source-over';
        for (const stroke of ground.strokes) stampStroke(bctx, stroke, content, dpr, progress);
        // Tint the alpha mask with the one accent, then lay it down as a wash.
        bctx.globalCompositeOperation = 'source-in';
        bctx.fillStyle = accent;
        bctx.fillRect(0, 0, W, H);
        ctx.globalAlpha = WASH_ALPHA * alpha * (0.4 + 0.6 * progress);
        ctx.drawImage(buffer, 0, 0);
    }
    ctx.globalAlpha = 1;
}
