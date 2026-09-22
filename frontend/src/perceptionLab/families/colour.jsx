import React from 'react';
import UnavailableFamily from './UnavailableFamily';

const reason = 'No Colour field producer is installed in this lane.';
export const SLOT = Object.freeze({ family: 'colour', label: 'Colour', available: false,
    reason, forms: [], operations: [], views: [], promptIntents: [],
    Panel: () => <UnavailableFamily label="Colour" reason={reason} /> });
