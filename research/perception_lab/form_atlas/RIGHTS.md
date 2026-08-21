# PERCEPTUAL-FORMS-001F — image identity and rights findings

Everything below was read from the holding institution's own record or its public API on
**2026-08-22**. Where a question did not resolve, it is recorded as unresolved rather than guessed:
a plausible-looking accession number is worse than none, because it gets copied.

**This lane commits no image bytes, for any entry, including the ones whose licence would permit
it.** The manifest points at a lawful source and records what a fetched copy must hash to. That
keeps a public repository clear of a rights question nobody has to answer, and it keeps the corpus
verifiable — a copy that does not match the digest is a different picture.

---

## The headline

Of the six works the build names, **two are in copyright until the 2040s** and **two more are
public-domain paintings whose only published reproductions are not freely licensed**. Only two of
the six can be lawfully fetched at full resolution and annotated.

| slot | artwork | reproduction | bytes fetchable |
| --- | --- | --- | --- |
| `van-steenwyck-courtyard` | PD (d. 1649) | CC BY-NC-**ND**, low-res only | **no** |
| `de-chirico-piazza` | **in copyright to 2049** | all rights reserved | **no** |
| `wells-nave` | building PD; photo 2014 | **CC BY-SA 3.0** | yes, with share-alike |
| `gris-cubist-interior` | **in copyright to 2044** (Picasso) | all rights reserved | **no** |
| `van-delen-gallery` | PD (d. 1671) | **PD Mark 1.0** (Rijksmuseum) | yes |
| `van-schooten-still-life` | PD (d. 1656) | **PD Mark 1.0** (Rijksmuseum) | yes |

The four adversarial controls are synthetic, already in this repository, and carry no rights
question at all — they are Lane C's, referenced by digest rather than redrawn.

---

## The distinction the whole corpus turns on

**A painting being out of copyright does not make a photograph of it free.** Van Steenwyck died in
1649 and NG141 is unarguably public domain; the National Gallery's photograph of it is a separate
work under separate terms. A manifest that recorded only the first fact would be wrong in the way
that gets a repository a letter.

Two of the six entries sit in exactly that gap, and both are recorded with `artwork_status` and
`reproduction_status` as separate fields for that reason.

The **ND** in the National Gallery's CC BY-NC-ND is the specific blocker, and it is worse than the
NC for this use: a benchmark's entire product is derivative. An annotation mask traced over an
image is an adaptation of it.

---

## The four unresolved questions

### 1. `van-delen-gallery` — the build's title does not resolve to any museum record

**"Perspective Fantasy of a Palace"** appears on print-reproduction and replica-selling sites and
on no institutional record found on the retrieval date. Two candidates were considered:

- **National Gallery NG1010, "An Architectural Fantasy", 1634** — closest to the build's title,
  and its reproductions are CC BY-NC-ND at low resolution only.
- **Rijksmuseum SK-A-3937, "Gallery of a Palace with Ornamental Architecture and Columns",
  1630–32** — a palace gallery rather than a city square, and freely licensed at full resolution.

**SK-A-3937 is the entry**, because a benchmark needs a picture it can lawfully use more than it
needs a title match. `identity.resolved` is `false` to keep the substitution visible.

**Needs a decision:** was the brief pointing at NG1010, at some third painting, or at a generic
"van Delen architectural fantasy"? If NG1010 specifically, the corpus loses full-resolution access
for that slot.

### 2. `gris-cubist-interior` — the named work is in copyright, and the substitute is imperfect

The brief asks for "a precisely identified Picasso/Cubist interior". Picasso died in 1973, so
**everything of his is in copyright until 1 January 2044**, actively licensed through Succession
Picasso (DACS/ARS). The named work — **The Architect's Table**, MoMA, Paris early 1912 — is pinned
by MoMA's object id 80280, but **its accession number did not resolve** from the public record and
is recorded as `unresolved`.

**Juan Gris (d. 1927) is the one major Cubist who is out of copyright by age**, and the proposed
stand-in is *Still Life before an Open Window, Place Ravignan* (1915), Philadelphia Museum of Art.
Two caveats travel with it and neither is fatal:

- The Commons file is tagged **PD-Art**, which rests on the doctrine that a faithful photograph of
  a two-dimensional public-domain work carries no new copyright. That is settled in the United
  States (*Bridgeman v. Corel*) and **contested in several EU member states**, so a corpus
  distributed in the EU inherits the argument.
- **The Met flags its own Gris holdings `isPublicDomain: false` with no published image** — all
  four objects checked (788081, 500382, 500424, 497126) are from the Leonard A. Lauder Cubist
  Collection and carry no open-access file. The artist being out of copyright by age did not make
  the Met a byte source for him, which is worth knowing before anyone plans around it.

**Needs a decision:** accept the Gris substitute and its PD-Art caveat, seek permission for the
Picasso, or drop the slot and rely on the `competing-extents` synthetic control — which tests the
same failure exactly and is what the matrix actually scores against.

### 3. `de-chirico-piazza` — in copyright, and no public-domain substitute was found

De Chirico died 20 November 1978; **Piazza d'Italia is in copyright until 1 January 2049**, with
rights held by Fondazione Giorgio e Isa de Chirico and administered through SIAE (ARS in the US).
Both layers are encumbered — the painting and any photograph of it — so nothing here may fetch,
store, or derive from it.

The identity itself resolved cleanly and is worth keeping: **de Chirico painted *Piazza d'Italia*
many times across five decades**, so the title alone identifies nothing. The atlas pins one canvas
— NGV **2022.854**, 1953, 50.0 × 40.2 cm — and any other version is a different picture with
different geometry.

**No public-domain substitute was identified.** The perceptual property this slot tests — flat
unmodelled masses with long detached cast shadows — is characteristic of a movement whose
principal figures all died after 1955.

**Needs a decision:** seek a licence, or accept that this slot is reference-only and that the
`competing-extents` control carries the test.

### 4. `wells-nave` — free, and the share-alike is a real obligation

**File:Wells Cathedral Nave 1, Somerset, UK - Diliff.jpg**, David Iliff, 2014-07-09, 5850 × 7000,
**CC BY-SA 3.0** (also offered under GFDL 1.2+). Required attribution:

> Photo by DAVID ILIFF. License: CC BY-SA 3.0

Not a licensing *problem*, but a licensing *consequence* worth stating before anyone builds on it:
**annotations traced over this image are adaptations, so any published mask set derived from it
must itself be CC BY-SA.** That is fine for a research corpus and incompatible with a proprietary
one. A lane that used the file without noticing would have licensed its own annotations by
accident.

Note also that the entry names **the photographer, not the architect**, in `identity.artist`. The
building is centuries out of copyright; the photograph is a 2014 work with a living author, and it
is the photograph the corpus uses. Conflating the two is the commonest rights error in image
corpora.

---

## What was checked and found clean

- **`van-schooten-still-life`** — Rijksmuseum **SK-A-2058**, c. 1630, 113 × 200 cm, **Public Domain
  Mark 1.0**, full-resolution download. The brief allowed "Floris van Schooten *or* a precisely
  identified Dutch still life"; van Schooten resolved precisely and freely, so the alternative
  branch was not needed.
- **`van-delen-gallery`** — Rijksmuseum **SK-A-3937**, PD Mark 1.0, full-resolution download. The
  rights are clean; only the identity is in question (see 1).
- **The four adversarial controls** — synthetic, drawn by
  `scripts/perception_lab_model_trials.py`, already committed by Lane C, referenced here by path
  and digest. `perception_lab_form_benchmark.py atlas` checks each digest against Lane C's own
  manifest, so the two lanes cannot drift into testing different pictures.

---

## If someone supplies an image

The schema supports it: `subject.kind = "user_supplied"` with a `digest`. The obligations are the
annotator's and the manifest records them rather than assuming them —

1. record where it came from and on what date;
2. record the licence or permission under which it was obtained;
3. record the digest of the exact file annotated, because a re-encode is a different picture and
   every mask in the record is on its raster;
4. do not commit the bytes to this repository.

## How to re-check this

Nothing here is frozen — a 2049 expiry is a date, and an institution can change its terms. Re-run:

```
python scripts/perception_lab_form_benchmark.py atlas
```

which validates the structure and the cross-lane digests but **cannot re-check a licence**. The
`retrieved` date on every rights block is what says how old these findings are.
