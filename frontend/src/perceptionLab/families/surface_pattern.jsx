import React from 'react';
import UnavailableFamily from './UnavailableFamily';

const reason = 'No Surface pattern producer is installed in this lane.';
export const SLOT = Object.freeze({ family: 'surface_pattern', label: 'Surface pattern / material',
    available: false, reason, forms: [], operations: [], views: [], promptIntents: [],
    Panel: () => <UnavailableFamily label="Surface pattern" reason={reason} /> });
