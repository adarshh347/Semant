# Gold reference masks — storage layout (currently empty)

No masks are stored yet. They were intentionally not generated in VISION-EVALSET-001
(the only in-repo mask tools are the candidates under evaluation, and the stop
condition forbids running candidates; gold masks also require human review). See
`../../gaps.md` §2.

When you create them, use:

```
fixtures/masks/
  <image_id>/                      e.g. CONF-a_5sculpt_695be6c9/
    <target_name>.png              one binary mask per critical target, native resolution
    PROVENANCE.md                  author · date · method · source image + dims · review status
```

- One PNG per critical target (from `../../targets.yaml`), not one per image.
- Masks stay separate from source images (this tree), never overwrite `../source/`.
- Record `provenance: human-reviewed` only after a human has corrected/approved the mask.
