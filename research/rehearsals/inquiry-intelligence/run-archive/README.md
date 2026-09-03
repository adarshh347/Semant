# Run archive

One directory per evaluation, each containing the manifest it ran against, the sanitized session,
the normalized evaluation, stage timing, provider/model identity, the structural metrics, the
diagnosis and the manual-review rubric.

`baseline-rev6/` is committed as the worked example. Everything else is gitignored: a run archive
carries a session verbatim, and deciding that a particular one should be public is a choice
somebody makes rather than a side effect of running the harness.
