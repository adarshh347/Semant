import React, { useState } from 'react';
import { buildExport, exportFilename, exportJson, verifyExport } from '../exportSession';
import { downloadText, serializeStage, snapshotLegend, svgToPngBlob } from '../snapshot';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — taking it out of the laboratory.
 *
 * TWO EXPORTS, BECAUSE THEY ARE TWO DIFFERENT CLAIMS:
 *
 *   THE RECORD    contract-exact JSON, validated by Lane A's own validators before it is written.
 *                 It is what was measured, refused and judged. If it will not validate it is not
 *                 written at all, because an export is read later by somebody who cannot ask what
 *                 it meant.
 *   THE PICTURE   what was on screen, with the execution identity and the derived-projection
 *                 sentence burnt into the image. A snapshot separated from its identity is a
 *                 picture of a mask with no way to tell whether an adapter ever ran.
 *
 * Neither is a promotion, and the panel says so where the buttons are — "export" is exactly the
 * word under which a hidden write into Semant would most comfortably hide.
 */
export default function ExportBar({ session, plans, runs, artifacts, reviews, run, artifact,
    clientIdentity, stageRef, now }) {
    const [status, setStatus] = useState(null);

    if (!session) return null;

    const bundleInput = {
        session, plans, runs, artifacts, reviews,
        exported_at: now(),
        client_identity: clientIdentity,
    };

    const problems = verifyExport(buildExport(bundleInput));

    const saveJson = () => {
        try {
            const at = now();
            const text = exportJson({ ...bundleInput, exported_at: at });
            const out = downloadText(exportFilename(session, at), text);
            setStatus({ ok: true, message: `${out.filename} · ${out.bytes} bytes` });
        } catch (err) {
            setStatus({ ok: false, message: String(err.message || err) });
        }
    };

    const saveSvg = () => {
        try {
            const at = now();
            const svg = serializeStage(stageRef?.current, {
                width: session.source.natural_width,
                height: session.source.natural_height,
                legend: snapshotLegend({ run, artifact, session, at }),
            });
            const out = downloadText(`perception-lab-${session.session_id}-${at}.svg`, svg,
                'image/svg+xml');
            setStatus({ ok: true, message: `${out.filename} · ${out.bytes} bytes` });
        } catch (err) {
            setStatus({ ok: false, message: String(err.message || err) });
        }
    };

    const savePng = async () => {
        try {
            const at = now();
            const svg = serializeStage(stageRef?.current, {
                width: session.source.natural_width,
                height: session.source.natural_height,
                legend: snapshotLegend({ run, artifact, session, at }),
            });
            const blob = await svgToPngBlob(svg);
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `perception-lab-${session.session_id}-${at}.png`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
            setStatus({ ok: true, message: `${a.download} · ${blob.size} bytes` });
        } catch (err) {
            // An honest refusal, not a blank rectangle that looks like an empty stage.
            setStatus({ ok: false, message: String(err.message || err) });
        }
    };

    return (
        <section className="pl-panel" aria-label="Export" data-export-bar>
            <div className="pl-panel-head">
                <h2 className="pl-panel-title">Export</h2>
                <span className="pl-chip" data-export-counts>
                    {artifacts.length} artifacts · {runs.length} runs · {reviews.length} verdicts
                </span>
            </div>

            {problems.length ? (
                <p className="pl-error" role="alert" data-export-invalid>
                    This session does not hold the contract and will not be exported:{' '}
                    {problems[0]}
                    {problems.length > 1 ? ` (and ${problems.length - 1} more)` : ''}
                </p>
            ) : null}

            <div className="pl-btnrow">
                <button type="button" className="pl-btn pl-btn--primary" data-action="export-json"
                    disabled={problems.length > 0} onClick={saveJson}>
                    The record, as JSON
                </button>
                <button type="button" className="pl-btn" data-action="export-svg"
                    onClick={saveSvg}>
                    The picture, as SVG
                </button>
                <button type="button" className="pl-btn" data-action="export-png"
                    onClick={savePng}>
                    The picture, as PNG
                </button>
            </div>

            {status ? (
                <p className={status.ok ? 'pl-panel-sub' : 'pl-error'}
                    role={status.ok ? undefined : 'alert'}
                    data-export-status={status.ok ? 'saved' : 'failed'}>
                    {status.message}
                </p>
            ) : null}

            <p className="pl-axisnote" data-export-consequence>
                An export is a copy. It mints no canonical id, it changes no lifecycle, and it
                puts nothing into Semant — there is no control on this page that could. The JSON
                is validated against <code>perception-lab.v1</code> before it is written, so a
                bundle that would not survive re-import is never produced.
            </p>
        </section>
    );
}
