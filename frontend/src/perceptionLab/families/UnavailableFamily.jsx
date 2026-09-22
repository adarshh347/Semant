import React from 'react';

export default function UnavailableFamily({ label, reason }) {
    return <section className="pl-panel" aria-label={`${label} family`}>
        <span aria-hidden="true">◇</span>
        <h2 className="pl-panel-title">{label} is unavailable</h2>
        <p className="pl-panel-sub">{reason}</p>
    </section>;
}
