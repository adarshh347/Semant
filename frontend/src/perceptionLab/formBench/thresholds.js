// PERCEPTUAL-FORMS-001H — the scalars that decided what a drawing looks like.
//
// A THRESHOLD THAT IS NOT ON SCREEN IS A DECISION NOBODY MADE. A soft field's cut, a density
// field's bandwidth, a field's declared value range and calibration, and a hypothesis's weight
// each change what a person sees, and a surface that applied one without showing it would let a
// reader take a choice for a measurement.
//
// This reads a payload and returns pairs. It applies nothing, hides nothing, and has no opinion
// about which of them matters — the panel prints all of them, in the order the record carries.

/** Every scalar in a payload that decides what gets drawn. */
export function thresholdsOf(record) {
    const payload = record?.payload || {};
    const found = [];
    if (payload.threshold_would_be !== undefined && payload.threshold_would_be !== null) {
        found.push(['threshold_would_be', payload.threshold_would_be]);
    }
    if (payload.smoothing?.applied) {
        found.push(['smoothing', `${payload.smoothing.method} @ ${payload.smoothing.bandwidth}`]);
    }
    if (payload.field?.value_range) {
        found.push(['value_range', payload.field.value_range.join(' – ')]);
    }
    if (payload.field?.calibration?.state) {
        found.push(['calibration', payload.field.calibration.state]);
    }
    (payload.hypotheses || []).forEach((h) => {
        if (h.weight !== null && h.weight !== undefined) found.push([h.hypothesis_id, h.weight]);
    });
    (payload.alternatives || []).forEach((a) => found.push([a.alternative_id, a.weight]));
    return found;
}
