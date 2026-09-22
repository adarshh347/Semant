import React from 'react';
import UnavailableFamily from './UnavailableFamily';

const reason = 'No Surface form producer is installed in this lane.';
export const SLOT = Object.freeze({ family: 'surface_form', label: 'Surface form', available: false,
    reason, forms: [], operations: [], views: [], promptIntents: [],
    Panel: () => <UnavailableFamily label="Surface form" reason={reason} /> });
