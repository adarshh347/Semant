// PERCEPTUAL-FORMS-001H — what each arm actually does, said next to the switch.
//
// Four arms, four levels, and the consequence of each is printed rather than discovered from a
// refusal. `Form` and `Recipe` both say what they DO NOT reach, because that is the surprising
// half: a derivation opens no image and loads no model, and a recipe reaches exactly the adapters
// its declared bounds allow and no others.
//
// In its own module because `ModeControls.jsx` exports a component and a file that exports both a
// component and a constant cannot be fast refreshed.

export const ARM_CONSEQUENCE = Object.freeze({
    direct: 'You choose the operation and its parameters. This establishes the organ without '
        + 'testing language.',
    form: 'You choose a form, a producer and the artifacts it reads. Nothing here opens the '
        + 'image or loads a model: a derivation computes from measurements this session already '
        + 'holds, and cannot become an artifact.',
    recipe: 'A bounded sequence of the same direct acts, declared in advance. It reaches the '
        + 'same resolver and the same adapter a pressed control does, within the bounds it '
        + 'printed before it ran.',
    prompt: 'You speak within the selected organ. The planner proposes a typed plan from a '
        + 'closed vocabulary; the same resolver and the same runner as Direct.',
});
