import { useEffect, useState } from 'react';
import { decodeFieldReference } from './fieldReference';

/** Raster display of retained values; no smoothing or new distance measurement. */
export default function useStoredField(ref) {
    const [result, setResult] = useState(null);
    useEffect(() => {
        let alive = true;
        setResult(null);
        if (!ref) return () => { alive = false; };
        decodeFieldReference(ref).then((field) => {
            if (!alive) return;
            const [h, w] = field.field_shape;
            const canvas = document.createElement('canvas');
            canvas.width = w; canvas.height = h;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
            ctx.fillRect(0, 0, 1, 1);
            const color = ctx.getImageData(0, 0, 1, 1).data;
            const image = ctx.createImageData(w, h);
            field.values.forEach((value, i) => {
                image.data[i * 4] = color[0]; image.data[i * 4 + 1] = color[1];
                image.data[i * 4 + 2] = color[2]; image.data[i * 4 + 3] = Math.round(value * 160);
            });
            ctx.putImageData(image, 0, 0);
            setResult({ imageUrl: canvas.toDataURL(), shape: field.field_shape });
        }).catch((error) => { if (alive) setResult({ error: error.message }); });
        return () => { alive = false; };
    }, [ref]);
    return result;
}
