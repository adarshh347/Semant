import React from 'react';
import UnavailableFamily from './UnavailableFamily';

const reason = 'No Depth field producer is installed in this lane.';
export const SLOT = Object.freeze({ family: 'depth', label: 'Depth', available: false,
    reason, forms: [], operations: [], views: [], promptIntents: [],
    Panel: () => <UnavailableFamily label="Depth" reason={reason} /> });
