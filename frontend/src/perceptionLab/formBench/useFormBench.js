import { useCallback, useEffect, useMemo, useState } from 'react';
import { supportsForms, unavailableBecause } from './formClient';

/**
 * PERCEPTUAL-FORMS-001H — the state behind the two new levels, and nothing else.
 *
 * ONE HOOK, TWO LEVELS, NO MEASUREMENT. This holds the form catalogue, the recipe catalogue, the
 * readiness answers and the derivations this session has produced. It computes no geometry,
 * decides no status and draws nothing: every number on screen came off the wire, and the renderers
 * are Lane E's.
 *
 * THE CATALOGUES ARE FETCHED ONCE AND THE READINESS IS NOT. A form's producers and a recipe's
 * steps are properties of the deployment; readiness is a property of THIS session, and a session
 * that selects a second artifact can become ready for a study it was not ready for a moment ago.
 * Caching the second would show a person a stale reason for a button they can now press.
 *
 * A FAILED FETCH IS AN ERROR OBJECT, NEVER AN EMPTY CATALOGUE. Nineteen forms and zero forms look
 * identical in a `.map()`, and a laboratory that showed an empty form list because a request
 * failed would be telling a person this deployment can do nothing.
 */
export default function useFormBench(client, { sessionId, ledger } = {}) {
    const [forms, setForms] = useState(null);
    const [recipes, setRecipes] = useState(null);
    const [readiness, setReadiness] = useState({});
    const [derivations, setDerivations] = useState([]);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState(null);
    const available = supportsForms(client);
    const unavailable = useMemo(() => unavailableBecause(client), [client]);

    const guard = useCallback(async (what, run) => {
        setBusy(true);
        setError(null);
        try {
            return await run();
        } catch (cause) {
            setError({ what, message: cause?.message || String(cause) });
            return null;
        } finally {
            setBusy(false);
        }
    }, []);

    useEffect(() => {
        if (!available) return undefined;
        let live = true;
        guard('read the form catalogue', async () => {
            const [f, r] = await Promise.all([client.forms(), client.recipes()]);
            if (!live) return null;
            setForms(f);
            setRecipes(r);
            return null;
        });
        return () => { live = false; };
    }, [available, client, guard]);

    useEffect(() => {
        if (!available || !sessionId) { setDerivations([]); return undefined; }
        let live = true;
        guard('read this session’s derivations', async () => {
            const body = await client.derivations({ session_id: sessionId });
            if (live) setDerivations(body?.derivations || []);
            return null;
        });
        return () => { live = false; };
    }, [available, client, guard, sessionId]);

    const checkRecipe = useCallback((key) => guard(`check ${key}`, async () => {
        const body = await client.recipeReadiness({ session_id: sessionId, key });
        setReadiness((held) => ({ ...held, [key]: body }));
        return body;
    }), [client, guard, sessionId]);

    /**
     * Compute one form. RETURNS THE WHOLE RECORD, refusals included.
     *
     * A derivation that refused is appended to the list exactly like one that produced a payload,
     * because "this input did not resolve" is a finding a person needs to be able to look at
     * afterwards, and a list that held only the successes would make a session look tidier than
     * it was.
     */
    const derive = useCallback((form, artifactIds, parameters) => guard(
        `derive ${form}`, async () => {
            const body = await client.derive({
                session_id: sessionId, form, artifact_ids: artifactIds, parameters,
            });
            if (body?.derivation) {
                setDerivations((held) => [...held, body.derivation]);
            }
            return body;
        }), [client, guard, sessionId]);

    const planRecipe = useCallback((key, bindings) => guard(
        `plan ${key}`, () => client.planRecipe({ session_id: sessionId, key, bindings })),
    [client, guard, sessionId]);

    /** The artifacts a form could read, by the input forms it declares. Never every artifact. */
    const inputsFor = useCallback((formKey) => {
        const entry = (forms?.forms || []).find((f) => f.form === formKey);
        const wanted = new Set(entry?.accepted_input_forms || []);
        const kindOf = { 'extent.hard_mask': 'extent_set',
            'topology.pair_relation': 'topology_relation_set' };
        const kinds = new Set([...wanted].map((f) => kindOf[f]).filter(Boolean));
        return (ledger || []).filter((a) => kinds.has(a.identity.artifact_kind));
    }, [forms, ledger]);

    return {
        available,
        unavailable,
        forms: forms?.forms || null,
        derivable: forms?.derivable || [],
        counts: forms?.counts || null,
        recipes: recipes?.recipes || null,
        readiness,
        derivations,
        busy,
        error,
        checkRecipe,
        derive,
        planRecipe,
        inputsFor,
    };
}
