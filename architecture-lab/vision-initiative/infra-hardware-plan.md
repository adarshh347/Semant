# Infra & hardware plan — what each machine lets us run

Maps Adarsh's hardware (4GB NVIDIA GPU now · AWS free plan · Mac Mini M4 16GB in ~1 month) to the Darshan model stack, and settles the serving strategy (Track B's **B1** decision). Grounded facts sourced at the end.

---

## 1. What each model actually needs

| Model | Role | Needs | Runs on 4GB GPU? | Runs on M4 16GB? | Verdict |
|---|---|---|---|---|---|
| **FashionCLIP** (ViT-B/32) | taste vectors + zero-shot labels + domain router | <1GB, **CPU-fine** | ✅ easily | ✅ easily (MPS/CPU) | **Local, anywhere.** Phase 1. |
| **YOLO11n-seg** | fast coarse anchors | ~6MB, CPU/GPU | ✅ | ✅ (MPS) | **Local, anywhere.** |
| **Fashionpedia** (Mask-RCNN) | garment parts + 294 attributes | ~3–5GB VRAM (inference) | ⚠️ borderline (small img, batch 1) | ✅ memory-fine; MPS ops patchy → CPU fallback works, slower | **Local prototype; serverless for throughput.** |
| **SAM2** | arbitrary regions + video | tiny 4GB · small 5GB · base+ 8GB · large 12GB VRAM | ⚠️ only **tiny**, image only | ⚠️ memory fits, **but Apple MPS support is broken (CUDA-only)** → CPU (slow) | **Serverless GPU** (esp. for video). |
| **Vision-LLM** (Groq llama-4-scout) | the felt reading / story | **API — no local GPU** | n/a | n/a | **API. No hardware concern.** |
| **RAG / vector store** | retrieval over Anuraṇana | CPU, tiny (512-dim vectors) | ✅ | ✅ | **Local, anywhere.** |

**The pattern:** the *vector + label + reading* layer (FashionCLIP, YOLO, LLM-API, RAG) is light and runs anywhere. Only the *heavy segmenters* (Fashionpedia at scale, SAM2, video) want a real GPU — and those are exactly where serverless earns its keep.

---

## 2. What each of your resources is good for

### 4GB NVIDIA GPU (now)
- **Fully covers:** FashionCLIP (all of Phase 1), YOLO. You can build and run the entire decision-light increment on this today — no blocker.
- **Marginal:** Fashionpedia inference (small images, batch 1), SAM2-**tiny** image-only.
- **Can't:** SAM2 base+/large, any **video**, any training.
- **Role:** your Phase-1 dev GPU + light Phase-2/3 experiments.

### AWS free plan — **correct the assumption: it is NOT free GPU**
- The 2026 free plan = **$200 credits, expiring in 6 months**, and EC2 is limited to **CPU-only** small instances (t3.micro/nano). **GPU instances are never free on AWS.**
- **Good for:** deploying the FastAPI backend, S3 storage, a live always-on demo, the CPU parts (low-volume FashionCLIP can even run CPU) — i.e. your **"deployed app" showcase asset**.
- The $200 credits *could* fund a short burst of GPU (a g4dn spot ~$0.5/hr) for one-off batch processing or a demo, but it drains fast and the 6-month clock is hard — treat it as a **capped experiment budget, not the serving plan.**
- **Role:** deployment + storage + a small, finite GPU experiment budget.

### Mac Mini M4 16GB (in ~1 month)
- Becomes your **primary dev machine**. 16GB *unified* memory beats the 4GB VRAM for memory-bound models.
- **Great for:** FashionCLIP, YOLO (MPS), the whole backend + Mongo + RAG locally, **Fashionpedia inference** (MPS/CPU, workable), full local integration testing of the image pipeline, running frontend+backend together for demos.
- **Caveat:** **SAM2 on Apple Silicon is currently painful** (CUDA-only kernels; MPS has known breakage) — so SAM2 and video you'll run **serverless, not on the M4.**
- **Role:** the everyday build + image-pipeline dev + demo machine.

---

## 3. The resulting serving strategy (settles Track B **B1**)

**Hybrid: local dev + serverless GPU for the heavy models + AWS for CPU hosting.**

- **Local (4GB now → M4 soon):** all development, Phase 1 (FashionCLIP), YOLO, Fashionpedia prototyping, RAG, the backend. Enough to *build and demo* the whole image pipeline.
- **Serverless GPU, pay-per-call** (Modal / Replicate / Runpod): Fashionpedia at throughput, **SAM2, and video** — precisely the models neither your 4GB GPU nor the M4 can serve well. Near-zero idle cost; you pay only when a request runs. **This is the answer to B1** (and it's exactly the "don't buy infra ahead of data" call we already locked for Track A).
- **AWS free credits:** deploy the CPU backend + storage + a live demo (strong portfolio/showcase value); keep GPU off AWS.

### Timeline
| When | What you can do |
|---|---|
| **Now (4GB GPU)** | Build **Track B Phase 1 (FashionCLIP)** locally — no blocker. Prototype Fashionpedia on small images. |
| **+1 month (M4 16GB)** | Full local image-pipeline dev; comfortable Fashionpedia inference; end-to-end integration + local demos. |
| **On demand (serverless GPU)** | Turn on SAM2 + video + any real throughput, pay-per-use. |
| **For the demo (AWS)** | Deploy the CPU backend + storage; live URL for portfolio/outreach. |

**Net:** nothing about the hardware blocks the plan. The image pipeline (Phases 1–3) is fully buildable on what you have; SAM2/video ride serverless GPU regardless of which machine you own; AWS gives you a deployed demo. This confirms **serverless-first** for B1 — not because we chose it abstractly, but because it's what your actual hardware requires.

## Sources
- [AWS Free Tier 2026 — $200 credits / 6 months / no GPU (AWS blog)](https://aws.amazon.com/blogs/aws/aws-free-tier-update-new-customers-can-get-started-and-explore-aws-with-up-to-200-in-credits/) · [AWS Free Tier FAQs](https://aws.amazon.com/free/free-tier-faqs/)
- [SAM2 variant VRAM (tiny 4GB · small 5GB · base+ 8GB · large 12GB) — facebookresearch/sam2 #118](https://github.com/facebookresearch/sam2/issues/118) · [SAM2 on Apple Silicon / MPS issues (#687, #34)](https://github.com/facebookresearch/sam2/issues/687)
- [FashionCLIP (ViT-B/32, CPU-OK) — HF](https://huggingface.co/patrickjohncyh/fashion-clip)
