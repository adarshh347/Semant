import { describe, expect, it } from 'vitest';
import { normalizeSession } from './inquiryContract';
import flower from '../../../contracts/samples/inquiry-session.constellation-flower.json';
import branching from '../../../contracts/samples/inquiry-session.constellation-branching.json';
import schema from '../../../contracts/samples/semantic-constellations.schema.json';

describe('canonical semantic constellation projection', () => {
    it.each([flower, branching])('keeps every strict record field through normalization and export', (raw) => {
        const session = normalizeSession(raw);
        const fields = Object.keys(schema.$defs.SemanticConstellation.properties).sort();
        expect(session.semantic_constellations.known).toBe(true);
        expect(session.semantic_constellations.current.length).toBeGreaterThan(0);
        for (const record of session.semantic_constellations.current) {
            expect(Object.keys(record).filter((k) => k !== 'graph_stale').sort()).toEqual(fields);
        }
        expect(session.semantic_constellations.current).toEqual(raw.semantic_constellations.current);
        expect(session.semantic_constellations.history).toEqual(raw.semantic_constellations.history);
        expect(session.raw).toEqual(raw);
        expect(session.checkpoint).toBe(raw.checkpoint);
    });
    it('missing data is not a negative preservation judgment', () => {
        expect(normalizeSession({}).semantic_constellations).toMatchObject({ recorded: false, current: [] });
    });
});
