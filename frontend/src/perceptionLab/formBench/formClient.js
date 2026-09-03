// PERCEPTUAL-FORMS-001H — the six methods that make the form levels possible, kept OFF the
// required interface.
//
// `REQUIRED_CLIENT_METHODS` is the twelve the laboratory cannot open without. These six are not
// added to it, and that is a decision rather than an oversight: a client that cannot serve the
// form catalogue is a client on an older backend, and the honest response is a laboratory that
// opens, works at the level it can, and SAYS the other two levels are unavailable here — not one
// that refuses to mount.
//
// So `FormBench` and `RecipeTray` ask `supportsForms(client)` and render a refusal naming the
// missing methods when the answer is no. A person on a stale deploy is told which wire they are
// on and what it cannot do, which is the same courtesy the capability table gives them about an
// adapter.
//
// THE FORBIDDEN LIST IS UNCHANGED AND STILL APPLIES. None of these six can promote anything;
// `assertNoPromotionSurface` is asserted about the same client in the same place it always was.

export const FORM_CLIENT_METHODS = Object.freeze([
    'forms', 'recipes', 'recipeReadiness', 'planRecipe', 'derive', 'derivations',
]);

/** Which of the six a client is missing. Empty means the two form levels are available. */
export function missingFormMethods(client) {
    return FORM_CLIENT_METHODS.filter((m) => typeof client?.[m] !== 'function');
}

export function supportsForms(client) {
    return missingFormMethods(client).length === 0;
}

/**
 * The sentence a level shows when the wire cannot serve it.
 *
 * Names the methods rather than saying "unavailable", for the reason the adapter table now gives
 * a reason: a person who is told only that something is unavailable goes looking for the wrong
 * thing.
 */
export function unavailableBecause(client) {
    const missing = missingFormMethods(client);
    if (!missing.length) return null;
    return `This wire does not serve ${missing.join(', ')}. The laboratory is talking to a `
        + 'backend without the form routes; direct operations and prompts still work.';
}
