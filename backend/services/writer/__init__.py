"""
Semant Writer (Track B · the manuscript half of the Chiasmatic circulation).

This package is a WRAPPER around the existing orchestration kernel, not a second system:

  - an *operator* is a Semant actuator authored by the writer from dialogue
    (`operators.py` is `director/capabilities.py`'s registry, made author-editable
    and persisted instead of compiled in),
  - the `//` orchestration layer is the Director's plan (`dsl.py`),
  - the render call is an actuator run: propose-never-commit, refusal-as-return-value
    (`render.py` mirrors `director/execution.py:ActuatorResult`),
  - Accept is the curator gate, and it commits into the *existing* sacred manuscript
    (`passages.py` writes through `manuscript_service`, which W1 does not fork).

Pure LLM orchestration (Groq). No specialist/vision models, no GPU, no weights.
"""
