import React from 'react';
import UnavailableFamily from './UnavailableFamily';

const reason = 'No Orientation field producer is installed in this lane.';
export const SLOT = Object.freeze({ family: 'orientation_flow', label: 'Orientation / flow',
    available: false, reason, forms: [], operations: [], views: [], promptIntents: [],
    Panel: () => <UnavailableFamily label="Orientation / flow" reason={reason} /> });
