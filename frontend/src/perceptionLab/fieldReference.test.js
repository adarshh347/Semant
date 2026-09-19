import { describe, expect, it } from 'vitest';
import { gzipSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import { decodeFieldReference } from './fieldReference';

function reference(body) {
    const bytes = gzipSync(JSON.stringify(body));
    return { uri: `data:application/gzip;base64,${bytes.toString('base64')}`,
        digest: `sha256:${createHash('sha256').update(bytes).digest('hex')}`, bytes: bytes.length };
}

describe('retained negative-space fields', () => {
    it('decodes exact samples and verifies the field digest', async () => {
        const field = { field_shape: [2, 2], values: [0, 1/3, 0.5, 1] };
        expect(await decodeFieldReference(reference(field))).toEqual(field);
    });
    it('refuses altered bytes, unsupported references and malformed dimensions', async () => {
        const ref = reference({ field_shape: [2, 2], values: [0, 1, 0, 1] });
        await expect(decodeFieldReference({ ...ref, digest: 'sha256:wrong' })).rejects.toThrow('digest');
        await expect(decodeFieldReference({ uri: 'https://unfetched.example/field' })).rejects.toThrow('supported');
        await expect(decodeFieldReference(reference({ field_shape: [2, 3], values: [0] }))).rejects.toThrow('dimensions');
    });
});
