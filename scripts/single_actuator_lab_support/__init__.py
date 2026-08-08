"""HARNESS-001C — the single-actuator orchestration laboratory.

RESEARCH ONLY. Nothing in this package defines a production entity, route, or Mongo
collection, and nothing in the running app imports it. It reads the live production seams —
`sam3_concept_service`, the Director's `concept_segment` actuator, its real runner — and
measures them from outside without changing them.

WHY IT EXISTS. A full orchestration run blends prompt interpretation, action choice, parameter
extraction, model availability, organ quality, wrapper conversion and stopping logic. When such
a run "produces nothing", that sentence names no layer. This lab locks execution to EXACTLY ONE
actuator and records every boundary, so the report can say which layer produced the outcome:

    organ succeeded, prompt phrase failed
    organ failed on a good control phrase
    organ succeeded but actuator conversion dropped data
    negative control correctly returned empty
    empty remains ambiguous pending review

THE FIREWALL COMES BEFORE THE INSTRUMENT. `firewall.py` is built first and every arm goes
through it, because a lab whose lock is enforced by the arms is a lab whose lock is one new arm
away from being gone.
"""
