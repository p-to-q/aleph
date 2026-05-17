#!/usr/bin/env python3
"""Live Aleph search API. The fixed local model θ is loaded ONCE at startup and
kept warm; each /search runs a fast shallow frontier search on arbitrary text.

Run:  python3 search/server.py     (→ http://localhost:8000)
"""
import sys, threading, time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

sys.path.insert(0, str(Path(__file__).parent))
import aleph_search as A  # noqa: E402

EVAL_MODEL = "mlx-community/Qwen3-1.7B-4bit"  # warm + fast for live use
QUICK_BUDGETS = [10, 30]
MAX_CHARS = 1200
LOCK_TIMEOUT = 300  # seconds; prevents infinite queue on MLX hang

_lock = threading.Lock()
_state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    t = time.time()
    _state["theta"] = A.Theta(EVAL_MODEL)
    _state["metric"] = A.Metric()
    _state["prop"] = A.Proposer(_state["theta"])
    print(f"[server] warm in {time.time()-t:.1f}s", flush=True)
    yield
    _state.clear()


app = FastAPI(title="Aleph live search", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class Req(BaseModel):
    text: str
    label: str | None = None


@app.get("/health")
def health():
    return {"ok": "theta" in _state, "model": EVAL_MODEL}


def _quick(theta, metric, prop, y):
    y = y.strip()[:MAX_CHARS]
    y_tok = theta.ntokens(y)
    max_out = int(y_tok * 1.5) + 32
    pts = []
    for K in QUICK_BUDGETS:
        best = None
        for cand in prop.propose(y, K, 2):
            got = theta.gen(cand, max_out)
            s = metric.sim(got, y)
            if best is None or s > best["similarity"]:
                best = {"prompt": cand, "similarity": s, "_got": got}
        lp = theta.ntokens(best["prompt"])
        pts.append({
            "epsilon": round(1.0 - best["similarity"], 4),
            "prompt": best["prompt"], "length": lp,
            "similarity": round(best["similarity"], 4), "stability": 1.0,
            "output": best["_got"],
        })
    idp = ("Repeat the following text exactly, verbatim, with no preamble, "
           "quotes, or commentary:\n\n" + y)
    gi = theta.gen(idp, int(y_tok * 1.4) + 32)
    sid = metric.sim(gi, y)
    explicit = {"epsilon": round(1.0 - sid, 4), "prompt": idp,
                "length": theta.ntokens(idp), "similarity": round(sid, 4),
                "stability": 1.0, "output": gi,
                "label": "Explicit Reconstruction"}
    try:
        toks, nll = theta.score(idp, y)
        if toks and len(toks) == len(nll):
            explicit["toktext"] = toks
            explicit["toknll"] = nll
    except Exception as e:
        print(f"[search] token NLL unavailable: {e}", flush=True)
    pts.append(explicit)
    return {"key": "custom", "label": "your text",
            "targetTokens": y_tok, "evalModel": EVAL_MODEL,
            "points": A.monotone(pts)}


@app.post("/search")
def search(req: Req):
    txt = (req.text or "").strip()
    if len(txt) < 8:
        return {"error": "give at least a sentence of target text"}
    if "theta" not in _state:
        return {"error": "model still warming up, try again in a moment"}
    t = time.time()
    if not _lock.acquire(timeout=LOCK_TIMEOUT):
        return {"error": "search engine busy — another search is running; try again shortly"}
    try:
        out = _quick(_state["theta"], _state["metric"], _state["prop"], txt)
    except Exception as e:  # never crash the server on a bad request
        return {"error": f"search failed: {e}"}
    finally:
        _lock.release()
    out["label"] = (req.label or txt[:48] + ("…" if len(txt) > 48 else ""))
    out["elapsed"] = round(time.time() - t, 1)
    print(f"[search] {out['elapsed']}s  |y|={out['targetTokens']}  "
          f"pts={len(out['points'])}", flush=True)
    return out


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
