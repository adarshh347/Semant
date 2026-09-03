/**
 * Soft Field painting (Differential v1).
 *
 * The one Ground type that lives on canvas, not SVG: brush strokes stamped as
 * radial-gradient passes into an alpha buffer (destination-out for subtract),
 * then tinted with the single --accent and laid down as a wash.
 *
 * Legibility (DIFF-UX-GATE-001 follow-up): a pure low-alpha wash disappears into
 * same-toned pixels and, unlike Path/Region, has no edge for the eye to catch. So
 * the wash is denser at its core AND carries a thin darker CONTOUR (a defining
 * rim, not a neon glow) so a field reads on any image and holds its own beside the
 * other ground types — while staying a soft field, not a line.
 *
 * ONE PASS PER INTENSITY LEVEL (brushIntensity.js). This used to be one buffer for
 * the whole ground, tinted once at one uniform alpha with the contour cast around
 * the combined silhouette. That is precisely the compositing that would flatten
 * four authored levels into a single wash — the semantic differences would reach
 * the canvas and then be averaged away at the last step. So the ground is now
 * drawn as one tinted pass per USED level, in ascending order, each with its own
 * recipe; `intensityPasses` owns that policy and is tested without a canvas.
 *
 * Everything here is pure drawing against the shared stage-geometry contract:
 * stroke points are normalized (0..1, natural-image space); `content` is the
 * letterboxed content box in CSS pixels. Bloom recall ramps radius + alpha 0→1.
 */

import { intensityPasses, stampAlphaFor } from './brushIntensity';

const STAMP_SPACING = 0.3;

function readVar(name, fallback) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
}
export const readAccent = () => readVar('--accent', '#5E2B50');
const readAccentDeep = () => readVar('--accent-deep', '#4A2140');

/**
 * Stamp one stroke into an alpha buffer. Denser core (holds to ~0.6 radius before
 * falling off) so the wash has body. Pressure scales the stamp RADIUS only —
 * never the semantic level, which is why `alpha` is passed in rather than read
 * off the gesture: intensity is authored, pressure is hardware.
 */
function stampStroke(bctx, stroke, content, dpr, progress, alpha) {
    const pts = stroke.points || [];
    if (!pts.length) return;
    const baseR = Math.max(2, (stroke.radius || 0.04) * content.w * dpr) * (0.65 + 0.35 * progress);
    const sub = stroke.op === 'sub';
    const strength = Math.min(1, alpha) * progress;
    bctx.globalCompositeOperation = sub ? 'destination-out' : 'source-over';

    const stamp = (x, y, pressure) => {
        const r = baseR * (0.6 + 0.4 * (pressure || 1));
        const a = sub ? 1 : strength;
        const g = bctx.createRadialGradient(x, y, 0, x, y, r);
        g.addColorStop(0, `rgba(255,255,255,${a})`);
        g.addColorStop(0.6, `rgba(255,255,255,${a * 0.9})`); // hold the core
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
    if (!ctx) return;   // no 2D context (e.g. jsdom) — nothing to paint, never throw
    ctx.clearRect(0, 0, W, H);
    if (!fields.length) return;

    const accent = color || readAccent();
    const accentDeep = readAccentDeep();
    const buffer = document.createElement('canvas');
    buffer.width = W; buffer.height = H;
    const bctx = buffer.getContext('2d');
    if (!bctx) return;

    for (const { ground, alpha = 1, progress = 1 } of fields) {
        if (!ground?.strokes?.length || progress <= 0 || alpha <= 0) continue;

        // Ascending level order: the image a curator gets does not depend on the
        // sequence they happened to paint in.
        for (const pass of intensityPasses(ground)) {
            bctx.clearRect(0, 0, W, H);
            bctx.globalCompositeOperation = 'source-over';
            for (const stroke of pass.add) {
                stampStroke(bctx, stroke, content, dpr, progress, stampAlphaFor(stroke, pass.level));
            }
            // Every erase cuts every level — the field shows what was taken away.
            for (const stroke of pass.sub) {
                stampStroke(bctx, stroke, content, dpr, progress, 1);
            }
            // Tint this level's alpha mask with the one accent. Hue never carries
            // the level; it stays the field/layer's own identity.
            bctx.globalCompositeOperation = 'source-in';
            bctx.fillStyle = accent;
            bctx.fillRect(0, 0, W, H);

            // The wash body at this level's alpha, with a tight darker rim cast
            // around its silhouette — a defining edge so it separates from
            // same-toned pixels the way a bordered ground does, without going
            // heavy/ink. The rim is the channel that survives a bright
            // background, so the denser levels repeat it rather than leaning on
            // alpha alone (which collapses on light pixels).
            const ramp = alpha * (0.45 + 0.55 * progress);
            ctx.save();
            ctx.shadowColor = accentDeep;
            ctx.shadowBlur = pass.recipe.rimBlur * dpr;
            ctx.globalAlpha = pass.recipe.body * ramp;
            ctx.drawImage(buffer, 0, 0);
            if (pass.recipe.rimBoost > 0) {
                ctx.globalAlpha = pass.recipe.rimBoost * ramp;
                ctx.drawImage(buffer, 0, 0);
            }
            ctx.restore();
        }
    }
    ctx.globalAlpha = 1;
}
