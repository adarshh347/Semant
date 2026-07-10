// Verification — Source Groups Phase 1, extension half.
//
// Executes the REAL functions from chrome-extension/content.js (queueSplit,
// captureFrames, massSaveQueue, postFrame) — not a re-implementation. The file is one
// IIFE with private functions, so we strip the wrapper and `return` the ones we need,
// then run them against a stubbed DOM and a fake seekable 10s video, intercepting the
// fetch bodies to read the source_group each frame would be saved with.
//
// Asserts the contract the task named: one shared group_id, sequence_index incrementing
// in capture order, monotonic t_ms — and the two ways real capture gets messy: a
// seek/decode miss (frame skipped, no push) must NOT misalign t_ms, and frames dropped
// in the review grid must renumber densely.

import fs from 'node:fs';
import vm from 'node:vm';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.join(HERE, '..', 'chrome-extension', 'content.js');
let src = fs.readFileSync(SRC, 'utf8');

// Unwrap the top-level IIFE and expose the internals we drive.
const open = src.indexOf('(function () {');
const bodyStart = src.indexOf('{', open) + 1;
const lastClose = src.lastIndexOf('})();');
let body = src.slice(bodyStart, lastClose);
body += '\n;return { queueSplit, captureFrames, massSaveQueue, postFrame, splitQueue };\n';

const results = [];
const check = (l, c, d = '') => { results.push(!!c); console.log(`  ${c ? 'PASS' : 'FAIL'}  ${l}${!c && d ? `\n          ${d}` : ''}`); };

// --- a permissive DOM element: any property read/method returns another element -------
function makeEl(tag = 'div') {
    const store = { tagName: (tag || '').toUpperCase(), _children: [] };
    const p = new Proxy(store, {
        get(t, k) {
            if (k in t) return t[k];
            if (k === 'classList') return { add() {}, remove() {}, toggle() {}, contains() { return false; } };
            if (k === 'style') return {};
            if (k === 'appendChild') return (c) => { t._children.push(c); return c; };
            if (k === 'append' || k === 'prepend' || k === 'before' || k === 'after') return () => {};
            if (k === 'addEventListener' || k === 'removeEventListener') return () => {};
            if (k === 'setAttribute' || k === 'removeAttribute' || k === 'focus' || k === 'blur'
                || k === 'remove' || k === 'scrollIntoView' || k === 'insertBefore') return () => {};
            if (k === 'querySelector') return () => makeEl();
            if (k === 'querySelectorAll') return () => [];
            if (k === 'getBoundingClientRect') return () => ({ x: 0, y: 0, width: 0, height: 0, top: 0, left: 0, right: 0, bottom: 0 });
            if (k === 'closest') return () => null;
            if (k === 'contains') return () => false;
            if (k === 'cloneNode') return () => makeEl(tag);
            if (typeof k === 'string') return makeEl();       // unknown prop → chainable element
            return undefined;
        },
        set(t, k, v) { t[k] = v; return true; },
    });
    return p;
}

// --- a fake seekable video: setting currentTime fires 'seeked' next microtask ---------
function makeVideo({ duration = 10, w = 720, h = 1280 } = {}) {
    const listeners = { seeked: [] };
    let _t = 0;
    const v = {
        duration, videoWidth: w, videoHeight: h,
        paused: true, muted: false, isConnected: true,
        get currentTime() { return _t; },
        set currentTime(x) { _t = x; queueMicrotask(() => listeners.seeked.forEach(f => f())); },
        pause() { this.paused = true; }, play() { this.paused = false; },
        addEventListener(ev, cb) { (listeners[ev] ||= []).push(cb); },
        removeEventListener(ev, cb) { listeners[ev] = (listeners[ev] || []).filter(f => f !== cb); },
    };
    return v;
}

// --- captured POST bodies -------------------------------------------------------------
const posted = [];
const sandbox = {
    console,
    crypto: { randomUUID: () => crypto.randomUUID() },
    setTimeout: (fn, ms) => setTimeout(fn, ms > 30 ? 5 : ms),   // speed the 60ms settles
    clearTimeout,
    setInterval: () => 0,
    clearInterval: () => {},
    queueMicrotask,
    Promise, Math, Date, Set, Map, JSON, Object, Array, Number, String, Boolean, Error,
    requestAnimationFrame: (fn) => setTimeout(fn, 0),
    cancelAnimationFrame: () => {},
    MutationObserver: class { observe() {} disconnect() {} },
    getComputedStyle: () => ({}),
    location: { href: 'https://instagram.com/reel/XYZ' },
    navigator: { userAgent: 'test' },
    fetch: async (_url, opts) => {
        try { posted.push(JSON.parse(opts.body)); } catch { /* ignore */ }
        return { ok: true, status: 201, json: async () => ({}) };
    },
    chrome: { storage: { sync: { get: async () => ({}) } } },
    addEventListener: () => {},
    removeEventListener: () => {},
    matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }),
};
sandbox.window = sandbox;
sandbox.document = new Proxy({}, {
    get(_t, k) {
        if (k === 'createElement') return (tag) => {
            if (tag === 'canvas') {
                return { width: 0, height: 0,
                         getContext: () => ({ drawImage() {} }),
                         toDataURL: () => 'data:image/jpeg;base64,FRAME' + Math.random().toString(36).slice(2, 8) };
            }
            return makeEl(tag);
        };
        if (k === 'body' || k === 'documentElement' || k === 'head') return makeEl();
        if (k === 'addEventListener' || k === 'removeEventListener') return () => {};
        if (k === 'querySelector') return () => makeEl();
        if (k === 'querySelectorAll') return () => [];
        if (k === 'getElementById') return () => null;
        if (k === 'createElementNS') return () => makeEl();
        return makeEl();
    },
});

vm.createContext(sandbox);
const api = vm.runInContext(`(function(){\n${body}\n})()`, sandbox, { filename: 'content.js' });

// -------------------------------------------------------------------------------------
async function run() {
    console.log('\n=== extension :: split a reel and read the stamped source_group ===');

    const video = makeVideo({ duration: 10 });     // total = clamp(8,60, round(10*3)) = 30
    api.queueSplit(video);
    const job = [...api.splitQueue.values()][0];
    check('a group_id was generated for the reel session', !!job.groupId, String(job.groupId));

    // Force one seek/decode miss mid-capture: zero the frame size on a single tick so the
    // loop `continue`s without pushing — the alignment trap.
    let flipped = false;
    const realW = Object.getOwnPropertyDescriptor(video, 'videoWidth');
    let tick = 0;
    Object.defineProperty(video, 'videoWidth', {
        get() { tick++; if (tick === 6 && !flipped) { flipped = true; return 0; } return 720; },
        configurable: true,
    });

    // wait for capture to finish
    for (let i = 0; i < 400 && job.state === 'capturing'; i++) await new Promise(r => setTimeout(r, 15));
    check('capture finished', job.state !== 'capturing', job.state);
    check('a skipped frame did not push a t_ms (frames and meta stay aligned)',
        job.frames.length === job.frameMeta.length, `${job.frames.length} frames vs ${job.frameMeta.length} meta`);
    check('the reel captured most of its frames', job.frames.length >= 25, `${job.frames.length} frames`);

    // t_ms must be strictly increasing across the whole capture (before any drops)
    const capTms = job.frameMeta.map(m => m.t_ms);
    check('captured t_ms is strictly monotonic',
        capTms.every((t, i) => i === 0 || t > capTms[i - 1]), JSON.stringify(capTms.slice(0, 6)) + '…');
    check('t_ms is the real video timestamp (ms), not the frame index',
        capTms[0] > 0 && capTms[capTms.length - 1] <= 10000 && capTms[capTms.length - 1] > 1000,
        `first=${capTms[0]} last=${capTms[capTms.length - 1]}`);

    // Drop two frames in the review grid, then mass-save.
    job.dropped.add(3);
    job.dropped.add(10);
    const keptCount = job.frames.length - job.dropped.size;

    posted.length = 0;
    const btn = makeEl('button');
    await api.massSaveQueue(btn);

    console.log(`  (posted ${posted.length} frames; captured ${job.frames.length}, dropped ${job.dropped.size})`);
    const groups = posted.map(b => b.source_group).filter(Boolean);
    check('every saved frame carried a source_group', groups.length === posted.length && groups.length > 0,
        `${groups.length}/${posted.length}`);
    check('the number saved equals captured minus dropped', posted.length === keptCount,
        `${posted.length} vs ${keptCount}`);
    check('all saved frames share the ONE reel group_id',
        new Set(groups.map(g => g.group_id)).size === 1 && groups[0].group_id === job.groupId);
    check('all are group_type="reel"', groups.every(g => g.group_type === 'reel'));

    const seq = groups.map(g => g.sequence_index);
    check('sequence_index is dense 0..k-1 over the SAVED frames',
        JSON.stringify(seq) === JSON.stringify([...Array(keptCount).keys()]), JSON.stringify(seq));
    check('sequence_total equals the saved count on every frame',
        groups.every(g => g.sequence_total === keptCount), String(groups[0]?.sequence_total));

    const tms = groups.map(g => g.t_ms);
    check('saved t_ms is monotonic in save order',
        tms.every((t, i) => i === 0 || t > tms[i - 1]), JSON.stringify(tms));
    // The kept frames must carry their TRUE captured timestamps — i.e. the captured
    // t_ms with the two dropped indices removed, in order. This proves t_ms is the real
    // video position, not a value renumbered to close the gap the drops left.
    const expectedTms = capTms.filter((_, i) => !job.dropped.has(i));
    check('saved t_ms are exactly the captured timestamps of the kept frames',
        JSON.stringify(tms) === JSON.stringify(expectedTms),
        `saved=${JSON.stringify(tms.slice(0, 5))}… expected=${JSON.stringify(expectedTms.slice(0, 5))}…`);

    // --- a single save carries group_type single, no group_id ------------------------
    posted.length = 0;
    await api.postFrame('data:image/x,AA', ['x'], {}, 'https://x', undefined);
    check('postFrame without a group sends NO source_group (single/carousel path)',
        posted[0] && posted[0].source_group === undefined, JSON.stringify(posted[0]?.source_group));

    const failed = results.filter(r => !r).length;
    console.log(`\n${results.length - failed} passed, ${failed} failed`);
    process.exit(failed ? 1 : 0);
}

run().catch(e => { console.error('HARNESS ERROR:', e); process.exit(2); });
