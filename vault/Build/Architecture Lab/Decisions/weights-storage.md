# WEIGHTS-001 — where the weights live, and how to get them

**Decision:** git holds a *manifest*; the weights themselves live in caches and are fetched.
No binary weight ever enters this repository.

The reason is asymmetric cost. A committed binary is immortal: it stays in history forever and
can only be removed by rewriting every commit after it — which breaks every clone, fork and open
PR. Adding one takes a second; removing one is a coordinated migration. So the policy is not
"clean them up later", it is **never add one**.

**Audit finding (2026-07-26): this repo has always been clean.** No weight file is tracked, none
ever was, `.git` is 69 MB. The `.gitignore` already covered `*.pt`; WEIGHTS-001 closed the
remaining formats (`*.pth`, `*.safetensors`, `*.onnx`, `*.ckpt`, `models/`). Deliberately *not*
a blanket `*.bin` — that extension is not exclusively weights, and nothing here tracks one today.

---

## The three files

| File | Role |
|---|---|
| `weights.manifest.json` | **in git.** Every model: kind, id, pinned revision, sha256, dest, size, licence, notes. |
| `scripts/fetch_weights.py` | **in git.** Reads the manifest and provisions idempotently. |
| the weights | **never in git.** `~/.cache/huggingface`, `~/.cache/torch`, `models/`, repo root. |

## Provisioning a fresh machine

```bash
pip install -r requirements.txt -r requirements-ml.txt   # includes the Intrinsic git dep
python scripts/fetch_weights.py --trust-hub-repos        # ~1.9 GB, idempotent
python scripts/fetch_weights.py --check                  # exit 0 == fully provisioned
```

`--check` downloads nothing and is the honest way to ask "am I provisioned?". A warm box
re-runs in ~5 s and fetches zero bytes.

### Why `--trust-hub-repos` is opt-in

`altered_midas` (an Intrinsic dependency) calls `torch.hub.load("rwightman/gen-efficientnet-pytorch")`
**without `trust_repo`**. On a fresh box that blocks on an interactive `y/N` prompt — invisible in
a container, and a hang rather than an error in CI. The flag pre-seeds torch's `trusted_list`,
which is exactly what answering `y` once does.

It is opt-in because it is a real consent decision: that repo is **executed code**, not weights,
pulled from a **branch tip** (`master`) with no pin. A fresh box gets whatever that branch says
that day. Low risk in practice — it is the `timm` author's repo — but the choice belongs to a
human, so the script names what it will trust and refuses to decide for you.

## Pinning

Every HF entry names a **commit sha**, never a branch. A floating `main` would silently swap the
model under us, and since every mark we mint carries a provenance receipt naming its model, a
silent swap would quietly falsify receipts already written — the marks would claim a model that
no longer exists as it did.

The pin is enforced, not merely recorded: each service declares `REVISION` and passes it to every
`from_pretrained`, and `AdapterSpec` carries a `revision` field mirroring the manifest.

### Scoping: `ignore_patterns` is load-bearing

`fashion_clip` carries `ignore_patterns: ["onnx/*", "pytorch_model.bin"]`. This is not a size
optimisation. The repo ships variants this codebase never loads (an ONNX directory; the legacy
`.bin` alongside safetensors). Without the scoping, `snapshot_download` considers the snapshot
**incomplete forever** — it raises `IncompleteSnapshotError` on every run and re-attempts a
download that would never be used. The local cache still holds 8 abandoned `.incomplete` ONNX
blobs from exactly that failure mode.

**The general rule: a manifest entry must describe the files we load, not the repo that hosts
them.** Otherwise "provisioned" never converges.

---

## Mirror plan — for the weights we do not control

Most entries are safe: HF repos at pinned shas, and PyTorch's own content-addressed CDN. Three
artifacts are not, and these are what a mirror is for:

| Artifact | Size | Risk |
|---|---|---|
| Intrinsic `final_weights.pt` | 485 MB | a **GitHub release asset** — upstream can retag or delete it. No HF mirror exists. The most fragile thing we depend on. |
| `yolo11n-seg.pt` | 5.9 MB | an Ultralytics release asset; Ultralytics also auto-downloads an *unpinned* version if absent. |
| `sam2.1_hiera_tiny.pt` | 148.8 MB | `dl.fbaipublicfiles.com` — stable, but not ours and not content-addressed. |

Combined ~640 MB — small enough for Supabase Storage, which we already run.

### Steps (documented, NOT executed — needs bucket credentials)

1. Create a private Supabase Storage bucket `model-weights`.
2. Upload the three files under `weights/<name>/<sha256-prefix>/<filename>` — **address by
   content hash, not by version label**, so a mirrored file can never quietly become a different
   file. This is the property the upstream sources lack.
3. Add a `mirror_url` field beside `url` in each `mirror_needed: true` manifest entry.
4. Teach `provision_url` to fall back to `mirror_url` when the primary 404s, verifying the same
   `sha256` either way — the hash makes the fallback safe by construction.
5. Verify by fetching from the mirror on a machine with an empty cache.

Move to R2/S3 if this grows past a few GB or needs public CDN reach; the manifest field is
storage-agnostic, so that swap is a URL change.

**Intrinsic's checkpoint should be mirrored first** — it is the largest, the least controlled, and
the only one with no alternative host.

## Open items

- `rwightman/gen-efficientnet-pytorch` and `facebookresearch/WSL-Images` are pulled from **branch
  tips**, unpinned. Pinning them means vendoring or patching `altered_midas`, so it is recorded
  rather than done.
- The Intrinsic pip dep itself tracks its default branch (`git+https://…` with no `@sha`). Pinning
  it is a one-line change once we know a good commit.
- `nvidia/segformer-b0-finetuned-ade-512-512` is under a **non-commercial research licence**, and
  `yolo11n-seg.pt` is **AGPL-3.0**. Both are fine for research; both need review before any
  commercial distribution. The manifest records this per entry.
