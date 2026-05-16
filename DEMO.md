# Aleph — demo script

**Thesis.** For a fixed model θ and a target output y, find a short prompt p that
regenerates y. The shortest such p approaches K(y | θ) — y's Kolmogorov
complexity *under the model*. We can't prove the minimum, so we report
**L̂(ε)** — the best known upper bound — as a rate–distortion curve.

## What is actually real (defendable in Q&A)

- **θ (evaluator) = local `Qwen3-4B-4bit` via MLX**, on this M4 Max. Fixed. This
  is the thesis: a frozen model is the decoder.
- **Proposer = the same local Qwen3** (no API key here) — the model proposes its
  own compressed prompts. The model literally compresses itself.
- **Distortion ε = 1 − cosine(embed(θ(p)), embed(y))**, sentence-transformers
  MiniLM. Greedy decode for scoring; sampled re-runs for `stability`.
- **L̂ curve = monotone lower envelope** of the measured points (best prompt with
  |p| ≤ L). Real data, just the frontier. Right end = identity prompt (paste y
  verbatim) → ε ≈ 0, the trivially-constructible upper bound.
- Page reads `web/public/aleph-frontier.json` (pipeline output). A real measured
  result is also **baked into the component** as fallback → the demo works even
  with no server/network.

## The click path (≈90s)

1. Open **http://localhost:3000/** (PC / full screen). Input screen: a paste box
   + example chips. Click an example (or paste + compress) → the result screen:
   logo, a morphing prompt/output, a draggable frontier, end labels
   `極限壓縮 · k(y|θ)` ↔ `顯式展開 · y itself`. Logo always returns to input.
2. Pick target **“Gettysburg Address”** (target line, center).
3. Drag the slider **right → left**:
   - far right: the identity prompt (paste the whole text), |p| ≈ |y|, ε ≈ 0.
   - middle (~26 tokens): **“Duplicate the opening of the Gettysburg Address …”**
     → ε ≈ **0.002**. Punchline: *a 26-token prompt regenerates Lincoln almost
     exactly — not because we sent the text, but because it’s already in θ.
     That’s the K(y|θ) end of the curve.*
   - far left (~9 tokens): a cryptic guess → ε jumps up. The frontier is real.
4. Open **dashboard** (top-right ▸) — real metrics: length |p|, similarity,
   stability, compression |p|/|y|, `L̂(ε ≈ …) — upper bound, not a proven
   minimum`, and **model θ = Qwen3-4B-4bit**.
5. Switch to **“A Tale of Two Cities”**: a *graded* tradeoff (ε 0.42 → 0.13 → 0)
   — not everything collapses to ε≈0; the curve has shape.
6. Switch to **“The Library of Babel”**: curve stays ~0.2 — an honest hard case.
   *L̂ is an upper bound; “we haven’t found shorter,” not “none exists.”*

Close: this is *compression-is-intelligence*, measured backwards — how short a
description of y already lives inside θ.

## If something breaks

Reload the page — real data is baked into the component. The demo never needs
the Python process or network at presentation time.

## Run / regenerate the data

```bash
cd ~/Desktop/Repositories/aleph
python3 search/aleph_search.py \
  --targets borges,dickens,gettysburg,genesis,hamlet \
  --eval-model mlx-community/Qwen3-4B-4bit --candidates 4 --refine 1 \
  --out search/frontier_rich.json
python3 search/finalize.py  --in search/frontier_rich.json   # → web/public/aleph-frontier.json (monotone)
python3 search/add_pitch.py                                   # → prepend the read-along pitch
```

**Frontend (self-contained, in this repo): `aleph/web/`**

```bash
cd ~/Desktop/Repositories/aleph/web && npm install && npm run dev   # → http://localhost:3000/
```

**Deploy:** Vercel project with **root directory = `web/`** (Next auto-detected,
zero config; `next build` verified clean, page is static-prerendered). The
precomputed demo works fully with **no backend**.

### Backend deploy (`search/server.py`)

The backend is **local-only by design**: it runs a fixed local Qwen3 via
**MLX**, which only works on Apple Silicon. It does **not** run on Vercel /
generic Linux x86. The deployed site's "compress your own text" degrades
gracefully if it's unreachable ("live search offline — examples still work").

**Recommended: run on the Mac + tunnel (no cloud GPU needed).**

```bash
# 1. backend on the Mac
cd ~/Desktop/Repositories/aleph
python3 -m venv .venv && source .venv/bin/activate
pip install -r search/requirements.txt
python3 search/server.py                      # -> http://localhost:8000

# 2. expose it (signup-free quick tunnel)
brew install cloudflared
cloudflared tunnel --url http://localhost:8000
# -> prints https://<random>.trycloudflare.com
```

Then set the frontend env var (no code change — `SEARCH_API` reads it):

- Local: `web/.env.local` → `NEXT_PUBLIC_SEARCH_API=https://<random>.trycloudflare.com/search`
- Vercel: Project → Settings → Environment Variables → `NEXT_PUBLIC_SEARCH_API` = the tunnel `/search` URL, then redeploy.

CORS is already open (`allow_origins=["*"]`). Quick-tunnel URLs change each run;
use a **named** cloudflared tunnel or Tailscale Funnel for a stable URL. The Mac
must be on during demos.

**Alternative (always-on, no Mac):** replace `Theta`/`Proposer` in
`search/aleph_search.py` with a non-MLX runtime (e.g. Qwen3 via vLLM/llama.cpp
on a GPU/CPU host: Modal, Fly GPU, Render, a VM) and deploy `server.py` there
with `search/requirements.txt` minus `mlx-lm`. This drops the "fixed *local*
model θ" framing — fine for hosting, weaker for the thesis. Not needed for the
hackathon (precomputed demo + Mac tunnel covers it).

## Honest limitations (say these before they ask)

Heuristic search (not optimal); embedding ε (semantic, not exact-match);
small 4-bit model; stability from 3 samples; proposer = evaluator (single model).
All on-thesis: Aleph reports a Pareto-frontier upper bound, not L*.
