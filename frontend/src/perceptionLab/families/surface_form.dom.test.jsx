import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, it } from 'vitest';
import fixture from '../../../../contracts/perception-lab-families/surface_form-normal-fixture.v1.json';
import SurfaceNormalPreview from './SurfaceNormalPreview';
import { SLOT } from './surface_form';

let container; let root;
beforeEach(() => {
    container = document.createElement('div'); document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(async () => {
    await act(async () => root.unmount()); container.remove();
});
const mount = async (node) => act(async () => root.render(node));
const click = async (node) => act(async () => node.dispatchEvent(new MouseEvent('click', { bubbles: true })));

it('shows the unavailable admission gap and labels the optional analytical view FIXTURE', async () => {
    await mount(<SLOT.Panel />);
    expect(container.textContent).toContain('Surface form is unavailable');
    expect(container.textContent).toContain('checkpoint permission');
    expect(container.textContent).toContain('No weights were downloaded or terms accepted');
    expect(container.querySelector('summary').textContent).toContain('FIXTURE only');
    expect(container.textContent).toContain('not a model estimate');
    expect(container.textContent).toContain('not physical curvature');
    expect([...container.querySelectorAll('button')].map((button) => button.textContent))
        .toEqual(['Read preview vector']);
});

it('exposes the two direction views, axis legend and keyboard-operable numerical probe', async () => {
    const before = JSON.stringify(fixture);
    await mount(<SurfaceNormalPreview data={fixture} />);
    expect(container.querySelectorAll('svg')).toHaveLength(2);
    expect(container.textContent).toContain('Fixed component scale −1 to +1');
    expect(container.textContent).toContain('camera Z (away from camera)');
    expect(container.textContent).toContain('right-handed');
    expect(container.textContent).toContain('not the object’s colour');
    expect(container.textContent).toContain('No camera calibration is implied');
    expect(container.querySelectorAll('label input')).toHaveLength(2);
    await click(container.querySelector('button'));
    expect(container.querySelector('[aria-live]').textContent).toContain('[1, 0, 0]');
    expect(JSON.stringify(fixture)).toBe(before);
});

it('shows invalid support as unknown, not a zero vector', async () => {
    const data = JSON.parse(JSON.stringify(fixture));
    data.preview.valid[0] = false; data.preview.values[0] = 0;
    await mount(<SurfaceNormalPreview data={data} />);
    await click(container.querySelector('button'));
    expect(container.querySelector('[aria-live]').textContent).toContain('invalid / unknown; no direction');
});

it('does not leave a previous reading visible after the selected field changes', async () => {
    await mount(<SurfaceNormalPreview data={fixture} />);
    await click(container.querySelector('button'));
    await mount(<SurfaceNormalPreview data={JSON.parse(JSON.stringify(fixture))} />);
    expect(container.querySelector('[aria-live]')).toBeNull();
});

it('refuses missing or incompatible data with a readable alert', async () => {
    await mount(<SurfaceNormalPreview data={null} />);
    expect(container.querySelector('[role="alert"]').textContent).toContain('Unsupported directed camera-normal');
    expect(container.querySelector('svg')).toBeNull();
});
