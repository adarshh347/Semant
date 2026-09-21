/** Decode a portable Lab field, verifying the bytes before reading the measurement. */
export async function decodeFieldReference(ref) {
    const prefix = 'data:application/gzip;base64,';
    if (!ref?.uri?.startsWith(prefix)) throw new Error('No supported stored field reference.');
    const bytes = Uint8Array.from(atob(ref.uri.slice(prefix.length)), (ch) => ch.charCodeAt(0));
    const hash = await crypto.subtle.digest('SHA-256', bytes);
    const digest = `sha256:${Array.from(new Uint8Array(hash), (b) => b.toString(16).padStart(2, '0')).join('')}`;
    if (digest !== ref.digest || (ref.bytes != null && ref.bytes !== bytes.length)) {
        throw new Error('Stored field digest or byte count mismatch.');
    }
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
    const field = JSON.parse(await new Response(stream).text());
    const [h, w] = field.field_shape || [];
    if (![h, w].every((v) => Number.isInteger(v) && v > 0) || field.values?.length !== h * w
        || !field.values.every((v) => Number.isFinite(v) && v >= 0 && v <= 1)) {
        throw new Error('Stored field dimensions or values are invalid.');
    }
    return field;
}
