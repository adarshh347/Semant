import React, { useEffect, useState } from 'react';
import './Registers.css';

/**
 * Semant Writer · W10 — the author declares their own layers.
 *
 * THE EMPTY STATE IS THE MOST IMPORTANT SCREEN IN THIS COMPONENT, and it deliberately does
 * not pre-fill anything. A fresh project shows no registers and an invitation to name the
 * layers the author actually works in. The classic ladder is behind a button that says what
 * it is — a starting point to edit — and adopting it only loads the rows into the FORM. It
 * is not saved until the author presses Declare.
 *
 * That distinction is the whole of the author's-ladder rule at the surface. A seeded list
 * would be indistinguishable from a decision the author made, and whatever ships as the
 * default becomes what most authors keep — so a default IS the imposed taxonomy, however
 * reasonable `surface / psychological / philosophical` reads.
 *
 * ORDER IS THE AUTHOR'S. They move rows; nothing here sorts them, scores them, or tells
 * them a register further down is "deeper". The position is recorded so the depth view can
 * show their ladder in their sequence, and it means nothing else anywhere in the system.
 */
export default function RegisterPanel({ onLoad, onDeclare, onLoadTemplate, onClose = null }) {
  const [rows, setRows] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const data = await onLoad();
        if (live) {
          setRows(data.registers || []);
          setLoaded(true);
        }
      } catch (err) {
        if (live) { setError(err.message || 'could not load your registers'); setLoaded(true); }
      }
    })();
    return () => { live = false; };
  }, [onLoad]);

  const edit = (i, field, value) =>
    setRows((current) => current.map((r, j) => (j === i ? { ...r, [field]: value } : r)));

  const move = (i, delta) => setRows((current) => {
    const next = [...current];
    const j = i + delta;
    if (j < 0 || j >= next.length) return current;
    [next[i], next[j]] = [next[j], next[i]];
    return next;
  });

  const declare = async () => {
    setBusy(true);
    setError('');
    setStatus('');
    try {
      const data = await onDeclare(
        rows.map((r) => ({ name: (r.name || '').trim(), description: r.description || '' }))
          .filter((r) => r.name),
      );
      setRows(data.registers || []);
      setStatus('These are your layers now.');
    } catch (err) {
      setError(err.message || 'that could not be declared');
    } finally {
      setBusy(false);
    }
  };

  const adoptTemplate = async () => {
    setError('');
    try {
      const proposed = await onLoadTemplate();
      // Into the FORM, not into the project. Nothing is stored until Declare.
      setRows(proposed.registers || []);
      setStatus('Loaded as a starting point — edit it, then declare it. Nothing is saved yet.');
    } catch (err) {
      setError(err.message || 'could not load the template');
    }
  };

  if (!loaded) return null;

  return (
    <section className="writer-registers" data-testid="register-panel">
      <header className="writer-registers__head">
        <h4>The layers you work in</h4>
        <p className="writer-registers__note">
          Your words, your order. Semant has no idea what depth is and never supplies one.
        </p>
        {onClose && (
          <button type="button" data-testid="registers-close" onClick={onClose}>close</button>
        )}
      </header>

      {rows.length === 0 && (
        <div className="writer-registers__empty" data-testid="registers-empty">
          <p>
            You have not named any layers yet — and nothing has been chosen for you.
            Name the ones you actually work in.
          </p>
          <button type="button" data-testid="adopt-template" onClick={adoptTemplate}>
            show me a common ladder to edit
          </button>
        </div>
      )}

      {rows.length > 0 && (
        <ol className="writer-registers__list" data-testid="register-rows">
          {rows.map((row, i) => (
            <li key={`row-${i}`} className="writer-register" data-testid="register-row">
              <input
                data-testid="register-name"
                value={row.name || ''}
                onChange={(e) => edit(i, 'name', e.target.value)}
                placeholder="a name for this layer"
                aria-label={`register ${i + 1} name`}
              />
              <input
                data-testid="register-description"
                value={row.description || ''}
                onChange={(e) => edit(i, 'description', e.target.value)}
                placeholder="what this layer is, to you"
                aria-label={`register ${i + 1} description`}
              />
              <span className="writer-register__moves">
                <button type="button" data-testid="register-up" aria-label="move up"
                  disabled={i === 0} onClick={() => move(i, -1)}>↑</button>
                <button type="button" data-testid="register-down" aria-label="move down"
                  disabled={i === rows.length - 1} onClick={() => move(i, 1)}>↓</button>
                <button type="button" data-testid="register-remove" aria-label="remove"
                  onClick={() => setRows((c) => c.filter((_, j) => j !== i))}>×</button>
              </span>
            </li>
          ))}
        </ol>
      )}

      <footer className="writer-registers__foot">
        <button type="button" data-testid="register-add"
          onClick={() => setRows((c) => [...c, { name: '', description: '' }])}>
          add a layer
        </button>
        <button type="button" data-testid="registers-declare" disabled={busy}
          onClick={declare}>
          {busy ? 'Declaring…' : 'Declare these'}
        </button>
        {status && <span className="writer-registers__status" data-testid="registers-status">
          {status}
        </span>}
      </footer>
      {error && <p className="writer-registers__error" data-testid="registers-error">{error}</p>}
    </section>
  );
}
