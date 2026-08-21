# PERCEPTUAL-FORMS-001F — the form atlas

The reference corpus: six real works and four adversarial controls, each resolved to an institution
and an accession number where one exists.

**No image bytes are committed by this lane, for any entry, including the ones whose licence would
permit it.** `atlas.json` points at a lawful source and records what a fetched copy must hash to.
That keeps a public repository clear of a rights question nobody has to answer, and keeps the corpus
verifiable: a copy that does not match the digest is a different picture.

Read **[RIGHTS.md](RIGHTS.md)** before using anything here. Short version: two of the six named works
are in copyright until the 2040s, two more are public-domain paintings whose only published
reproductions are not freely licensed, and one is freely licensed **under share-alike**, which is an
obligation on any annotations derived from it.

## Structure of an entry

| field | why it exists |
| --- | --- |
| `identity` | the work, pinned. `resolved: false` where the build's title matched no museum record |
| `rights.artwork_status` | is the *painting* in copyright |
| `rights.reproduction_status` | is the *photograph of it* freely licensed — a separate question, and the one corpora usually get wrong |
| `rights.may_commit_bytes` + `why_not` | a committable source names its licence; anything else says why not |
| `rights.attribution` / `retrieved` | what must be said, and how old the finding is |
| `access.how` | `reference_only`, `manifest_pointer`, or `in_repository` |
| `access.digest` | what a fetched copy must hash to |
| `open_access_alternate` | a freely licensed work of the same perceptual structure, where one exists — a stand-in for the *measurement*, never for the identity |
| `why_this_work` | what perceptual property put this picture in the corpus |

`identity.resolved` and `rights.resolved` are separate because they fail separately: a work can be
pinned to an accession number and be unusable, and be freely licensed and be the wrong picture.

Validate with:

```
python scripts/perception_lab_form_benchmark.py atlas
```

which checks the structure, that nothing claims committed bytes, and that every `in_repository`
reference matches the digest Lane C's own manifest records for it — so the two lanes cannot drift
into testing different pictures.
