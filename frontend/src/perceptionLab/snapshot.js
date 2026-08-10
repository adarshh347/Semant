// PERCEPTUAL-ORGANS-002 Lane E — a picture of what was on the screen.
//
// A display snapshot is evidence of a DRAWING, and it is worth exporting for exactly the reason it
// is dangerous: it is the artefact most likely to be pasted into a document and read as a
// measurement. So the snapshot carries a legend, burnt into the image, saying what it is — the
// execution identity, the artifact, and the sentence that the overlays were computed in a browser.
// A snapshot that could be cropped free of that legend would be a picture of a mask with no way to
// tell whether an adapter ever ran.
//
// SVG FIRST, PNG SECOND, and that order is deliberate. The stage is already SVG over an <img>
// whose src is a data URI, so serializing it is lossless and needs nothing from the platform.
// Rasterizing to PNG needs a canvas, which is not always there — and when it is not, this REFUSES
// with a sentence rather than producing a blank rectangle that looks like an empty stage.

const XMLNS = 'http://www.w3.org/2000/svg';

/**
 * Serialize a stage element to a standalone SVG document.
 *
 * Styles are inlined as a small explicit stylesheet rather than copied from the page, because a
 * snapshot that depended on the app's CSS would render differently — or blankly — anywhere else.
 */
export function serializeStage(stage, { width, height, legend = [] } = {}) {
    if (!stage) throw new Error('there is no stage to snapshot');
    const img = stage.querySelector('img');
    const svgs = [...stage.querySelectorAll('svg')];
    if (!svgs.length) {
        throw new Error('the stage has no overlay to snapshot — nothing has been drawn on it');
    }
    const w = width || 1200;
    const h = height || Math.round(w * 0.75);
    const legendHeight = legend.length ? 18 * legend.length + 16 : 0;

    const layers = svgs.map((svg) => {
        const inner = svg.innerHTML;
        const viewBox = svg.getAttribute('viewBox') || `0 0 ${w} ${h}`;
        return `<svg x="0" y="0" width="${w}" height="${h}" viewBox="${viewBox}" `
            + `preserveAspectRatio="xMidYMid meet">${inner}</svg>`;
    }).join('\n');

    const legendLines = legend.map((line, i) => `<text class="pl-snap-legend" x="12" `
        + `y="${h + 22 + i * 18}">${escapeText(line)}</text>`).join('\n');

    return `<svg xmlns="${XMLNS}" xmlns:xlink="http://www.w3.org/1999/xlink" `
        + `width="${w}" height="${h + legendHeight}" viewBox="0 0 ${w} ${h + legendHeight}">
<style>
  .pl-snap-bg { fill: #ffffff; }
  .pl-snap-legend { font: 13px ui-monospace, monospace; fill: #1a1a1a; }
  .rs-shape { fill: rgba(90,120,200,0.22); stroke: #3a5bbf; stroke-width: 2; }
  .rs-shape--box, .rs-shape--manual { stroke-dasharray: 6 4; }
  .rs-shape--manual { stroke: #7d4a86; fill: rgba(125,74,134,0.18); }
  .pl-band { fill: rgba(190,120,70,0.45); stroke: #a4652f; stroke-width: 1.5; }
  .pl-intersection { fill: rgba(140,100,190,0.5); stroke: #6b4b9a; stroke-width: 1.5; }
  .pl-endpoint-line { stroke: #1a1a1a; stroke-width: 2; fill: none; }
  .pl-endpoint-dot { fill: #1a1a1a; }
  .pl-freehand { fill: none; stroke: #7d4a86; stroke-width: 2; stroke-dasharray: 4 3; }
  .pl-wash-cell { stroke: none; color: #3a5bbf; }
</style>
<rect class="pl-snap-bg" x="0" y="0" width="${w}" height="${h + legendHeight}" />
${img?.src ? `<image x="0" y="0" width="${w}" height="${h}" `
        + `preserveAspectRatio="xMidYMid meet" href="${escapeAttr(img.src)}" />` : ''}
${layers}
${legendLines}
</svg>`;
}

/**
 * The legend that has to travel with the picture.
 *
 * Not decoration. A snapshot separated from its execution identity is a picture of a mask with no
 * way to tell whether an adapter ever ran on the image, and that is the single most misreadable
 * artefact this laboratory can produce.
 */
export function snapshotLegend({ run, artifact, session, at }) {
    const lines = [];
    lines.push(`Perception Lab · ${at}`);
    if (run) {
        lines.push(`${run.execution_identity} · run ${run.run_id} · outcome ${run.outcome}`
            + `${run.replay ? ` · replay of ${run.replay.source_run_id}, nothing was called` : ''}`);
    } else {
        lines.push('no run — nothing on this image was produced by an organ');
    }
    if (artifact) {
        lines.push(`${artifact.identity.artifact_id} · ${artifact.identity.operation} · `
            + `${artifact.measurement.epistemic_status} on a `
            + `${artifact.measurement.epistemic_basis} basis · lifecycle `
            + `${artifact.lifecycle.status}`);
    }
    if (session) lines.push(`image ${session.source.image_digest}`);
    lines.push('Overlays were computed in a browser to show where the measurement lives. '
        + 'They are not the measurement.');
    return lines;
}

/**
 * SVG → PNG, or an honest refusal.
 *
 * Rejects rather than resolving to something blank. A snapshot that silently produced an empty
 * rectangle would be indistinguishable from a stage with nothing on it.
 */
export function svgToPngBlob(svgText, { width, height } = {}) {
    return new Promise((resolve, reject) => {
        if (typeof document === 'undefined' || typeof Image === 'undefined') {
            reject(new Error('there is no document here to rasterize with'));
            return;
        }
        const canvas = document.createElement('canvas');
        let ctx = null;
        try {
            ctx = canvas.getContext('2d');
        } catch {
            ctx = null;
        }
        if (!ctx || typeof canvas.toBlob !== 'function') {
            reject(new Error('this environment has no 2D canvas, so a PNG cannot be rasterized. '
                + 'The SVG snapshot is complete and lossless — use that.'));
            return;
        }
        const dims = readSize(svgText, { width, height });
        canvas.width = dims.width;
        canvas.height = dims.height;
        const image = new Image();
        image.onload = () => {
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, dims.width, dims.height);
            ctx.drawImage(image, 0, 0, dims.width, dims.height);
            canvas.toBlob((blob) => {
                if (blob) resolve(blob);
                else reject(new Error('the canvas produced no image'));
            }, 'image/png');
        };
        image.onerror = () => reject(new Error('the snapshot SVG could not be decoded'));
        image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgText)}`;
    });
}

function readSize(svgText, { width, height }) {
    const w = width || Number(svgText.match(/\bwidth="(\d+)"/)?.[1]) || 1200;
    const h = height || Number(svgText.match(/\bheight="(\d+)"/)?.[1]) || 900;
    return { width: w, height: h };
}

const escapeText = (s) => String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const escapeAttr = (s) => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;');

/** Hand a string to the browser as a download. The one place this module touches the DOM. */
export function downloadText(filename, text, mime = 'application/json') {
    const blob = new Blob([text], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    return { filename, bytes: blob.size };
}
