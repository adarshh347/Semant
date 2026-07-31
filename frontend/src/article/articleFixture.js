/**
 * CIRCUIT-003 M4 — the article fixture for the /lab/article harness.
 *
 * PROVENANCE, because a fixture that looks like real output must say how real it is:
 * this payload is a REAL `resolve_article()` result — a real M2 ArgumentPlan, composed by the
 * real M3 Groq composer, confirmed against a chain, and joined to real geometry by the real M4
 * resolver. The prose, the caveats, the qualifications, the counter-reading and the AMBIGUOUS
 * citation are all genuine output, captured verbatim.
 *
 * TWO ENTRIES ARE HARNESS-AUTHORED, and are marked here rather than blended in: one
 * `relevance_flags` entry on §1 and one `uncited_mentions` entry on §3. M3 emits exactly these
 * shapes — its own guarded run produced the identical pressure-zone relevance flag — but the
 * composer is non-deterministic and this harness exists to exercise the failure path every time.
 * Rendering an article that only ever shows the happy path would tell you nothing about the
 * artifact's actual job.
 *
 * Source images are generated as data-URI canvases at call time, so the harness fetches nothing.
 */

const PALETTE = {
    post_lustgarten: ['#8FA48C', '#C9C3A6', '#5C6B57'],
    post_facade: ['#B9AE99', '#6E6455', '#D8D0BC'],
    post_rotunda: ['#7E7490', '#C6BBD1', '#4A4358'],
};

/** A stand-in source image. Distinct per post, so a percept drawn on the wrong one is obvious. */
function fixtureImage(postId, w = 900, h = 675) {
    if (typeof document === 'undefined') return '';
    const [a, b, c] = PALETTE[postId] || ['#999', '#ccc', '#666'];
    const cv = document.createElement('canvas');
    cv.width = w; cv.height = h;
    const ctx = cv.getContext('2d');
    if (!ctx) return '';
    const g = ctx.createLinearGradient(0, 0, w, h);
    g.addColorStop(0, a); g.addColorStop(0.55, b); g.addColorStop(1, c);
    ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = 'rgba(255,255,255,0.22)'; ctx.lineWidth = 1.5;
    for (let i = 1; i < 8; i += 1) {
        ctx.beginPath(); ctx.moveTo((i / 8) * w, h * 0.32); ctx.lineTo((i / 8) * w, h); ctx.stroke();
    }
    ctx.fillStyle = 'rgba(255,255,255,0.10)';
    ctx.beginPath(); ctx.ellipse(w * 0.5, h * 0.5, w * 0.28, h * 0.3, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = 'rgba(20,18,16,0.55)';
    ctx.font = '600 26px system-ui, sans-serif';
    ctx.fillText(postId.replace('post_', ''), 24, 44);
    return cv.toDataURL('image/png');
}

const PAYLOAD = {
    "version": 1,
    "draft": {
        "version": 1,
        "thesis": "The Altes Museum converts a dispersed civic ground into a centralized interior; the sequence performs the conversion rather than merely housing it.",
        "thesis_prose": "The article argues that the Altes Museum converts a dispersed civic ground into a centralized interior, and that the architectural sequence itself enacts this conversion rather than simply containing it. It observes, in a measured but qualified sense, that the Lustgarten disperses attention across the whole frame. It then shows that the colonnade\u2019s repetitive rhythm begins to gather that dispersal, and that the rotunda completes the gathering at a single centre.",
        "epistemic": "measured",
        "grounded": true,
        "complete": false,
        "committed": false,
        "sections": [
            {
                "claim_id": "c0",
                "claim": "The Lustgarten disperses attention across the whole frame.",
                "function": "support",
                "prose": "The measured pressure zone marks where the composition concentrates in the Lustgarten. Because this measurement identifies a focal concentration, it does not show that attention is dispersed across the whole frame. Consequently, the evidence does not directly support the claim of dispersion.",
                "epistemic": "measured",
                "qualified": true,
                "caveats": [
                    "aimed to be 'visible', reached 'measured'",
                    "pressure_zone does not bear on this claim: it indicates concentration rather than dispersion",
                    "pressure_zone does not bear on this claim: it measures where attention concentrates, not whether it is spread"
                ],
                "citations": [
                    {
                        "step_id": "c0:0:pressure_zone",
                        "actuator": "pressure_zone",
                        "function": "support",
                        "epistemic": "measured",
                        "image": "post_lustgarten",
                        "image_title": "Lustgarten",
                        "shows": "Where the composition concentrates.",
                        "attribution": null
                    }
                ],
                "relevance_flags": [
                    {
                        "step_id": "c0:0:pressure_zone",
                        "actuator": "pressure_zone",
                        "why": "it measures where attention concentrates, not whether it is spread"
                    }
                ],
                "dropped_citations": [],
                "uncited_mentions": []
            },
            {
                "claim_id": "c1",
                "claim": "The colonnade's repetition begins to gather that dispersal into a rhythm.",
                "function": "complicate",
                "prose": "The measured observation notes repetition and interval across the colonnade\u2019s surface. This measured rhythm hints that the colonnade\u2019s repeated elements begin to gather the dispersed visual field into a patterned cadence, complicating the notion that the Lustgarten solely disperses attention across the whole frame.",
                "epistemic": "measured",
                "qualified": false,
                "caveats": [],
                "citations": [
                    {
                        "step_id": "c1:0:rhythm",
                        "actuator": "rhythm",
                        "function": "complicate",
                        "epistemic": "measured",
                        "image": "post_facade",
                        "image_title": "Colonnade",
                        "shows": "Repetition and interval across the surface.",
                        "attribution": null
                    }
                ],
                "relevance_flags": [],
                "dropped_citations": [],
                "uncited_mentions": []
            },
            {
                "claim_id": "c2",
                "claim": "The rotunda completes the gathering at a single centre.",
                "function": "support",
                "prose": "The measured pressure zone on the rotunda indicates where the composition concentrates. This focal concentration shows that the rotunda serves as the single centre that completes the gathering.",
                "epistemic": "measured",
                "qualified": true,
                "caveats": [],
                "citations": [
                    {
                        "step_id": "c2:0:pressure_zone",
                        "actuator": "pressure_zone",
                        "function": "support",
                        "epistemic": "measured",
                        "image": "post_rotunda",
                        "image_title": "Rotunda",
                        "shows": "Where the composition concentrates.",
                        "attribution": null
                    }
                ],
                "relevance_flags": [],
                "dropped_citations": [],
                "uncited_mentions": [
                    "post_lustgarten"
                ]
            }
        ],
        "uncomposed": [],
        "counter_reading": {
            "grounded": true,
            "prose": "If the Rotunda shown in the image is not actually present, the claim that the Altes Museum creates a centralized interior collapses, because the supposed focal point for the conversion is missing. Without that architectural element, the sequence cannot be said to perform the conversion of a dispersed civic ground. However, the evidence is merely a binary presence check, so its force is limited and easy to dismiss if the image is ambiguous.",
            "citations": [
                {
                    "step_id": "c2:1:presence_check",
                    "actuator": "presence_check",
                    "function": "challenge",
                    "epistemic": "measured",
                    "image": "post_rotunda",
                    "image_title": "Rotunda",
                    "shows": "Is the named thing actually there?",
                    "attribution": null
                }
            ],
            "absence_reason": "",
            "absence_detail": ""
        },
        "qualifications": [
            {
                "claim_id": "c0",
                "claim": "The Lustgarten disperses attention across the whole frame.",
                "status": "supported",
                "prose": "The claim that the Lustgarten disperses attention across the whole frame. is carried, but not in the way it was aimed at: it sought 'visible' evidence and rests on 'measured'.",
                "why": "all_percepts_bound"
            },
            {
                "claim_id": "c3",
                "claim": "The rotunda's stone recurs from the colonnade's.",
                "status": "refused",
                "prose": "This reading could not establish that the rotunda's stone recurs from the colonnade's. No evidence for it could be produced from this corpus, so the point is left open rather than argued.",
                "why": "no_percept_could_be_produced"
            }
        ],
        "notes": [
            "confirmed against a run before composing",
            "a percept was reported as not bearing on its claim; those sections are qualified"
        ],
        "run_id": "run_altes_m4",
        "model": "openai/gpt-oss-120b"
    },
    "resolved": {
        "c0:0:pressure_zone": {
            "step_id": "c0:0:pressure_zone",
            "actuator": "pressure_zone",
            "function": "support",
            "epistemic": "measured",
            "status": "resolved",
            "image": "post_lustgarten",
            "image_ref": "http://x/lustgarten.jpg",
            "image_title": "Lustgarten",
            "attribution": null,
            "geometry": {
                "kind": "soft_mask",
                "strokes": [
                    {
                        "points": [
                            [
                                0.16,
                                0.42
                            ]
                        ],
                        "radius": 0.1,
                        "strength": 0.45,
                        "op": "add"
                    },
                    {
                        "points": [
                            [
                                0.34,
                                0.55
                            ]
                        ],
                        "radius": 0.1,
                        "strength": 0.45,
                        "op": "add"
                    },
                    {
                        "points": [
                            [
                                0.5,
                                0.48
                            ]
                        ],
                        "radius": 0.1,
                        "strength": 0.45,
                        "op": "add"
                    },
                    {
                        "points": [
                            [
                                0.66,
                                0.58
                            ]
                        ],
                        "radius": 0.1,
                        "strength": 0.45,
                        "op": "add"
                    },
                    {
                        "points": [
                            [
                                0.84,
                                0.45
                            ]
                        ],
                        "radius": 0.1,
                        "strength": 0.45,
                        "op": "add"
                    },
                    {
                        "points": [
                            [
                                0.25,
                                0.72
                            ]
                        ],
                        "radius": 0.1,
                        "strength": 0.45,
                        "op": "add"
                    },
                    {
                        "points": [
                            [
                                0.58,
                                0.75
                            ]
                        ],
                        "radius": 0.1,
                        "strength": 0.45,
                        "op": "add"
                    },
                    {
                        "points": [
                            [
                                0.78,
                                0.68
                            ]
                        ],
                        "radius": 0.1,
                        "strength": 0.45,
                        "op": "add"
                    }
                ]
            },
            "geometry_kind": "soft_mask",
            "label": "pressure zone",
            "source_ref": "post_lustgarten:pressure_zone",
            "detail": "",
            "candidates": [],
            "drawable": true,
            "reopen": {
                "post_id": "post_lustgarten",
                "source_ref": "post_lustgarten:pressure_zone",
                "step_id": "c0:0:pressure_zone"
            }
        },
        "c1:0:rhythm": {
            "step_id": "c1:0:rhythm",
            "actuator": "rhythm",
            "function": "complicate",
            "epistemic": "measured",
            "status": "resolved",
            "image": "post_facade",
            "image_ref": "http://x/facade.jpg",
            "image_title": "Colonnade",
            "attribution": null,
            "geometry": {
                "kind": "soft_mask",
                "strokes": [
                    {
                        "points": [
                            [
                                0.08,
                                0.56
                            ]
                        ],
                        "radius": 0.045,
                        "strength": 0.8,
                        "op": "add"
                    },
                    {
                        "points": [
                            [
                                0.185,
                                0.56
                            ]
                        ],
                        "radius": 0.045,
                        "strength": 0.8,
                        "op": "add"
                    },
                    {
                        "points": [
                            [
                                0.29,
                                0.56
                            ]
                        ],
                        "radius": 0.045,
                        "strength": 0.8,
                        "op": "add"
                    },
                    {
                        "points": [
                            [
                                0.395,
                                0.56
                            ]
                        ],
                        "radius": 0.045,
                        "strength": 0.8,
                        "op": "add"
                    },
                    {
                        "points": [
                            [
                                0.5,
                                0.56
                            ]
                        ],
                        "radius": 0.045,
                        "strength": 0.8,
                        "op": "add"
                    },
                    {
                        "points": [
                            [
                                0.605,
                                0.56
                            ]
                        ],
                        "radius": 0.045,
                        "strength": 0.8,
                        "op": "add"
                    },
                    {
                        "points": [
                            [
                                0.71,
                                0.56
                            ]
                        ],
                        "radius": 0.045,
                        "strength": 0.8,
                        "op": "add"
                    },
                    {
                        "points": [
                            [
                                0.815,
                                0.56
                            ]
                        ],
                        "radius": 0.045,
                        "strength": 0.8,
                        "op": "add"
                    },
                    {
                        "points": [
                            [
                                0.92,
                                0.56
                            ]
                        ],
                        "radius": 0.045,
                        "strength": 0.8,
                        "op": "add"
                    }
                ]
            },
            "geometry_kind": "soft_mask",
            "label": "rhythm",
            "source_ref": "post_facade:rhythm",
            "detail": "",
            "candidates": [],
            "drawable": true,
            "reopen": {
                "post_id": "post_facade",
                "source_ref": "post_facade:rhythm",
                "step_id": "c1:0:rhythm"
            }
        },
        "c2:0:pressure_zone": {
            "step_id": "c2:0:pressure_zone",
            "actuator": "pressure_zone",
            "function": "support",
            "epistemic": "measured",
            "status": "resolved",
            "image": "post_rotunda",
            "image_ref": "http://x/rotunda.jpg",
            "image_title": "Rotunda",
            "attribution": null,
            "geometry": {
                "kind": "soft_mask",
                "strokes": [
                    {
                        "points": [
                            [
                                0.5,
                                0.5
                            ]
                        ],
                        "radius": 0.17,
                        "strength": 1.0,
                        "op": "add"
                    },
                    {
                        "points": [
                            [
                                0.5,
                                0.5
                            ]
                        ],
                        "radius": 0.1,
                        "strength": 1.0,
                        "op": "add"
                    }
                ]
            },
            "geometry_kind": "soft_mask",
            "label": "pressure zone",
            "source_ref": "post_rotunda:pressure_zone",
            "detail": "",
            "candidates": [],
            "drawable": true,
            "reopen": {
                "post_id": "post_rotunda",
                "source_ref": "post_rotunda:pressure_zone",
                "step_id": "c2:0:pressure_zone"
            }
        },
        "c2:1:presence_check": {
            "step_id": "c2:1:presence_check",
            "actuator": "presence_check",
            "function": "challenge",
            "epistemic": "measured",
            "status": "ambiguous",
            "image": "post_rotunda",
            "image_ref": "http://x/rotunda.jpg",
            "image_title": "Rotunda",
            "attribution": null,
            "geometry": null,
            "geometry_kind": "",
            "label": "",
            "source_ref": "",
            "detail": "2 produced percepts match 'presence_check' on post_rotunda; none was chosen because a suggestion does not record its step",
            "candidates": [
                "rotunda:presence:a",
                "rotunda:presence:b"
            ],
            "drawable": false,
            "reopen": {
                "post_id": "post_rotunda",
                "source_ref": "",
                "step_id": "c2:1:presence_check"
            }
        }
    },
    "images": [
        "post_lustgarten",
        "post_facade",
        "post_rotunda"
    ],
    "counts": {
        "citations": 4,
        "drawable": 3,
        "unresolved": 1
    }
};

/** The resolved article, with fixture images swapped in for the (unfetchable) source URLs. */
export default function articleFixture() {
    const payload = JSON.parse(JSON.stringify(PAYLOAD));
    for (const r of Object.values(payload.resolved || {})) {
        if (r.image) r.image_ref = fixtureImage(r.image);
    }
    return payload;
}
