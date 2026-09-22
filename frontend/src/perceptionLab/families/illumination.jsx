import React from 'react';
import UnavailableFamily from './UnavailableFamily';

const reason = 'No Illumination field producer is installed in this lane.';
export const SLOT = Object.freeze({ family: 'illumination', label: 'Illumination', available: false,
    reason, forms: [], operations: [], views: [], promptIntents: [],
    Panel: () => <UnavailableFamily label="Illumination" reason={reason} /> });
