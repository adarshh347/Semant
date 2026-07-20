# Source fixtures — provenance

Seven real Semant images, fetched read-only from the curator's own Cloudinary
delivery URLs (cloud `dxxyyglus`) on **2026-07-18** for `VISION-EVALSET-001`. No
stored post data was modified; these are local snapshots so the corpus is
reproducible if a URL rots or a post is re-dissected. All are the curator's own
uploaded assets — treat as private project data, not for redistribution.

Cloudinary bakes/strips EXIF on delivery (all seven report `exif_orientation=none`),
so these snapshots will **not** reproduce the EXIF-orientation defect the code audit
flagged (P0-1) — that risk lives on the *original upload* path, before Cloudinary.
To test EXIF handling you need an original rotated-EXIF file (see `../gaps.md`).

| file | post_id | dims (W×H) | aspect | mode | what it actually is (viewed) | stored `domain` guess |
|---|---|---|---|---|---|---|
| `a_5sculpt_695be6c9.jpg` | 695be6c9a9ea58f1b6aef5e0 | 680×286 | 2.378 | RGB | Five heritage sculpture **heads** side by side on black — Solanki · Gupta · Pala · Amaravati · Gandhara — with white text labels. The REGION-GEOMETRY-001 regression image. | `product` (0.97) ✗ |
| `b_product_695be786.jpg` | 695be786a9ea58f1b6aef5ed | 452×679 | 0.666 | RGB | A single ornate carved stone **female figure** (sensuous torso, elaborate jewelled hairdress), dramatic raking side-light, dense carved ornament, grey gradient studio ground. | `product` (0.99) ✗ |
| `c_photo_695be794.jpg` | 695be794a9ea58f1b6aef5f1 | 454×679 | 0.669 | RGB | Weathered **stone statue of a woman** (memorial), black-and-white, bare winter branches behind, soft atmospheric depth, eroded/lichened surface. | `photography` (0.99) ✓ |
| `d_fashion_695be8ba.jpg` | 695be8baa9ea58f1b6aef609 | 643×680 | 0.946 | RGB | An **oil painting** — a figure seen close, a black **lace/tulle bow** at the throat over bare décolletage, warm ochre ground, painterly dissolving edges, artist signature lower-left. | `fashion` (0.48) partial |
| `e_arch_695be77e.jpg` | 695be77ea9ea58f1b6aef5eb | 544×680 | 0.800 | RGB | Michelangelo's **Pietà inside St Peter's** — white marble group in an ornate architectural niche with cross, pilasters, lanterns; dramatic light shaft; grungy textured composite. | `architecture` (0.93) ✓ |
| `f_product_695be7fa.jpg` | 695be7faa9ea58f1b6aef5f7 | 445×680 | 0.654 | RGB | A vintage **lithograph/engraving of Vishnu** seated on the coiled serpent Śeṣa under a seven-hooded nāga canopy; Thai caption (พระนารายณ์); aged paper, ruled border, radiating light ground. | `product` (0.94) ✗ |
| `g_dataset_001.png` | (repo `datasets/images/001.png`; source acct likely `@shrishhart`) | 998×1192 | 0.837 | RGBA | A colour **photograph of four people** posing indoors (two women in saris — one orange/gold check, one maroon — with gold jewellery; two men in shirts), arms overlapping; a fifth face half-cut at the right edge; Instagram carousel arrow overlaid. | (not run) |

**Domain-guess accuracy:** 2 of 6 stored guesses are right (`c`, `e`); 4 are wrong —
heritage sculpture and a devotional lithograph are both called `product`. This is
itself scored evidence for the domain-parsing rubric (`../rubric.md` §Semantics) and
corroborates the code audit's "DomainProfile is implicit and unreliable" finding.
