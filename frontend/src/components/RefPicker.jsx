import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Star, Crosshair, Eye } from 'lucide-react';
import './RefPicker.css';

const hasNote = (r) => !!(r.user_note || '').trim();

/**
 * The picker `/part` and `/lens` open at the caret.
 *
 * Ordering is the whole design. An image can carry forty regions, and the one the
 * curator means is almost never the fortieth polygon the detector happened to find —
 * it is the part they starred, or wrote a note about. So: prioritised first, then
 * noted, then everything else, each group in the pane's own order. The list a person
 * scans should be sorted by what they cared about, not by what a model emitted.
 *
 * Keyboard mirrors SlashMenu exactly (↑/↓/Enter/Esc), because this opens from the same
 * "/" gesture and a different set of keys here would be a small betrayal.
 */
export default function RefPicker({ kind, regions, lenses, x, y, onPick, onClose }) {
    const [index, setIndex] = useState(0);
    const [query, setQuery] = useState('');
    const inputRef = useRef(null);

    useEffect(() => { inputRef.current?.focus(); }, []);
    useEffect(() => setIndex(0), [query, kind]);

    const items = useMemo(() => {
        const q = query.toLowerCase().trim();
        if (kind === 'lens') {
            return (lenses || [])
                .filter(l => !q || (l.name || '').toLowerCase().includes(q))
                .map(l => ({
                    id: l.name,
                    title: l.name,
                    sub: l.reading || '',
                    badge: (l.region_ids || []).length
                        ? `${l.region_ids.length} part${l.region_ids.length !== 1 ? 's' : ''}`
                        : 'no parts',
                    raw: l,
                }));
        }
        const rank = (r) => (r.prioritised ? 0 : hasNote(r) ? 1 : 2);
        return (regions || [])
            .filter(r => !q
                || (r.label || '').toLowerCase().includes(q)
                || (r.category || '').toLowerCase().includes(q))
            .map((r, i) => ({ r, i }))
            .sort((a, b) => rank(a.r) - rank(b.r) || a.i - b.i)
            .map(({ r }) => ({
                id: r.id,
                title: r.label || 'part',
                sub: [r.category, r.material].filter(Boolean).join(' · '),
                starred: !!r.prioritised,
                noted: hasNote(r),
                raw: r,
            }));
    }, [kind, regions, lenses, query]);

    const pick = (i) => { const it = items[i]; if (it) onPick(it.raw); };

    const onKeyDown = (e) => {
        if (e.key === 'Escape') { e.preventDefault(); onClose(); }
        else if (e.key === 'ArrowDown') { e.preventDefault(); setIndex(i => (i + 1) % Math.max(1, items.length)); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); setIndex(i => (i + items.length - 1) % Math.max(1, items.length)); }
        else if (e.key === 'Enter') { e.preventDefault(); pick(index); }
    };

    return (
        <div className="ref-picker" style={{ position: 'fixed', left: x, top: y + 6, zIndex: 95 }}
            role="dialog" aria-label={kind === 'lens' ? 'Cite a lens' : 'Point at a part'}>
            <div className="ref-picker-head">
                {kind === 'lens' ? <Eye size={13} /> : <Crosshair size={13} />}
                <input
                    ref={inputRef}
                    className="ref-picker-input"
                    placeholder={kind === 'lens' ? 'Which lens?' : 'Which part?'}
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={onKeyDown}
                    // Blurring closes, but a click on a row must land first — the row
                    // preventDefaults its mousedown, so blur never fires ahead of it.
                    onBlur={onClose}
                />
            </div>

            {items.length === 0 ? (
                <div className="ref-picker-empty">
                    {kind === 'lens' ? 'No lenses match.' : 'No parts match.'}
                </div>
            ) : (
                <div className="ref-picker-list" role="listbox">
                    {items.map((it, i) => (
                        <button
                            key={it.id}
                            type="button"
                            role="option"
                            aria-selected={i === index}
                            className={`ref-picker-item${i === index ? ' is-selected' : ''}`}
                            onMouseEnter={() => setIndex(i)}
                            onMouseDown={(e) => { e.preventDefault(); pick(i); }}
                        >
                            <span className="ref-picker-body">
                                <span className="ref-picker-title">
                                    {it.title}
                                    {it.starred && <Star size={11} fill="currentColor" className="ref-picker-star" />}
                                    {it.noted && !it.starred && <span className="ref-picker-dot" title="has a note" />}
                                </span>
                                {it.sub && <span className="ref-picker-sub">{it.sub}</span>}
                            </span>
                            {it.badge && <span className="ref-picker-badge">{it.badge}</span>}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
