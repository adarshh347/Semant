import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import OrchestrationBar from './OrchestrationBar';

/**
 * CIRCUIT-001 SURFACE-001 — the intention affordance, fake-driven (no network).
 *
 * Proves the last mile: typing an intention → the endpoint's plan is SHOWN (including refused
 * steps, with their reason) → the returned suggestions are handed to store.ingestSuggestions (the
 * existing review path). No review UI is built here; the bar only routes into it.
 */
let container; let root;
async function mount(node) { await act(async () => { root.render(node); }); }
async function flush() { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); }
beforeEach(() => { container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container); });
afterEach(async () => { await act(async () => { root.unmount(); }); container.remove(); vi.restoreAllMocks(); });

const RESPONSE = {
  intention: 'trace the light',
  plan: {
    steps: [{ step_id: 's1', actuator: 'light_field', params: {}, note: '' },
            { step_id: 's2', actuator: 'shadow_field', params: {}, note: '' }],
    refused: [{ step_id: 's3', actuator: 'semantic_read', reason: 'missing_input',
                detail: "'semantic_read' needs region and nothing in this plan provides it" }],
    notes: [],
  },
  suggestions: [
    { producer: 'light_field', type: 'brush_field', role: 'light_field',
      geometry: { kind: 'soft_mask', strokes: [{ points: [[0.5, 0.5]], radius: 0.05 }] },
      provenance: { model: 'intrinsic', adapter: 'intrinsic' }, confidence: 0.65 },
    { producer: 'shadow_field', type: 'brush_field', role: 'shadow_field',
      geometry: { kind: 'soft_mask', strokes: [{ points: [[0.3, 0.3]], radius: 0.05 }] },
      provenance: { model: 'intrinsic', adapter: 'intrinsic' }, confidence: 0.6 },
  ],
  provenance: {
    lineage: [{ step_id: 's1', actuator: 'light_field', status: 'ok' },
              { step_id: 's2', actuator: 'shadow_field', status: 'ok' }],
    gaps: [{ step_id: 's3', actuator: 'semantic_read', status: 'refused', why: 'needs region' }],
  },
  weakest_link: 0.6, complete: false,
};

function fakeFetch(response) {
  return vi.fn().mockResolvedValue({ ok: true, json: async () => response });
}

describe('OrchestrationBar — SURFACE-001', () => {
  it('runs an intention, shows the plan + the refused step, and ingests suggestions', async () => {
    global.fetch = fakeFetch(RESPONSE);
    const ingested = [];
    const store = { ingestSuggestions: (d) => { ingested.push(...d); return d; } };

    await mount(<OrchestrationBar postId="p1" store={store} />);

    const input = container.querySelector('.orch-input');
    // React controlled input: set through the native value setter so onChange fires.
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    await act(async () => { setter.call(input, 'trace the light'); input.dispatchEvent(new Event('input', { bubbles: true })); });
    await flush();
    await act(async () => { container.querySelector('.orch-run').click(); });
    await flush();

    // the plan is shown: two steps that ran + the refused one with its reason
    const names = [...container.querySelectorAll('.orch-step-name')].map((n) => n.textContent);
    expect(names).toContain('light_field');
    expect(names).toContain('shadow_field');
    expect(names).toContain('semantic_read');
    expect(container.querySelector('.orch-step.is-refused')).not.toBeNull();
    expect(container.textContent).toMatch(/refused/);

    // the suggestions were routed into the existing quarantine (not a new surface)
    expect(ingested.map((s) => s.role)).toEqual(['light_field', 'shadow_field']);

    // fetch hit the orchestrate endpoint with the intention
    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [, opts] = global.fetch.mock.calls[0];
    expect(global.fetch.mock.calls[0][0]).toMatch(/\/orchestrate$/);
    expect(JSON.parse(opts.body).intention).toBe('trace the light');
  });

  it('readings (presence/count) never reach the quarantine', async () => {
    global.fetch = fakeFetch({
      intention: 'is there an angel', plan: { steps: [{ step_id: 's1', actuator: 'presence_check', params: {}, note: '' }], refused: [], notes: [] },
      suggestions: [{ type: 'presence_reading', phrase: 'angel', present: true }],
      provenance: { lineage: [{ step_id: 's1', actuator: 'presence_check', status: 'ok' }], gaps: [] },
      weakest_link: null, complete: true,
    });
    const ingested = [];
    const store = { ingestSuggestions: (d) => { ingested.push(...d); return d; } };
    await mount(<OrchestrationBar postId="p1" store={store} />);
    const input = container.querySelector('.orch-input');
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    await act(async () => { setter.call(input, 'is there an angel'); input.dispatchEvent(new Event('input', { bubbles: true })); });
    await act(async () => { container.querySelector('.orch-run').click(); });
    await flush();
    expect(ingested).toEqual([]);            // a reading is a sentence, not a mark
  });
});
