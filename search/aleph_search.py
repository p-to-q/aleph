#!/usr/bin/env python3
"""Aleph search: for a fixed local model θ and a target output y, search the
prompt space for short prompts p that regenerate y, producing the rate-distortion
frontier  L̂(ε) = min known |p| s.t. d(θ(p), y) ≤ ε.

θ (evaluator) is a fixed local Qwen3 via mlx-lm — this IS the thesis.
The proposer (Claude via API) only *suggests* candidate prompts; it never
evaluates. Distortion ε = 1 − cosine(embed(θ(p)), embed(y)).

Usage:
  python aleph_search.py --targets borges --out frontier.json \
      --candidates 4 --refine 1 --eval-model auto
"""
import argparse, json, os, re, statistics, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from targets import TARGETS  # noqa: E402

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
EVAL_CANDIDATES = ["mlx-community/Qwen3-4B-4bit", "mlx-community/Qwen3-1.7B-4bit"]
BUDGETS = [6, 12, 25, 50, 100]  # approx prompt token budgets (left→right)
_SKIP_STABILITY = False


# ---------- evaluator: the fixed local model θ ----------
class Theta:
    def __init__(self, repo):
        from mlx_lm import load
        print(f"[θ] loading {repo} ...", flush=True)
        t = time.time()
        self.model, self.tok = load(repo)
        self.repo = repo
        print(f"[θ] loaded in {time.time()-t:.1f}s", flush=True)

    def _fmt(self, p):
        msgs = [{"role": "user", "content": p}]
        try:
            return self.tok.apply_chat_template(
                msgs, add_generation_prompt=True, tokenize=False,
                enable_thinking=False,
            )
        except TypeError:
            return self.tok.apply_chat_template(
                msgs, add_generation_prompt=True, tokenize=False)

    def gen(self, p, max_tokens, temp=0.0):
        from mlx_lm import generate
        kw = {}
        if temp and temp > 0:
            from mlx_lm.sample_utils import make_sampler
            kw["sampler"] = make_sampler(temp=temp)
        out = generate(self.model, self.tok, prompt=self._fmt(p),
                        max_tokens=max_tokens, verbose=False, **kw)
        return THINK_RE.sub("", out).strip()

    def ntokens(self, s):
        return len(self.tok.encode(s))

    def score(self, prompt, target):
        """Teacher-forced per-token NLL of `target` given `prompt`, under θ.
        One full forward pass (no sampling): logits[pos] predicts seq[pos+1],
        so y_ids[t] is scored from position (len(fmt)+t-1). Returns
        (token_strings, nll_per_token) aligned 1:1. English targets only —
        per-token decode can render oddly on multi-byte/CJK tokens."""
        import mlx.core as mx
        import mlx.nn as nn
        fmt_ids = self.tok.encode(self._fmt(prompt))
        y_ids = self.tok.encode(target)
        if not y_ids:
            return [], []
        logits = self.model(mx.array([fmt_ids + y_ids]))
        logp = nn.log_softmax(logits[0].astype(mx.float32), axis=-1)
        base = len(fmt_ids)
        toks, nlls = [], []
        for t, tid in enumerate(y_ids):
            lp = float(logp[base + t - 1, tid])
            toks.append(self.tok.decode([tid]))
            nlls.append(round(-lp, 4))
        return toks, nlls


# ---------- distortion metric ----------
class Metric:
    def __init__(self):
        self.kind = "embed"
        try:
            from sentence_transformers import SentenceTransformer
            self.m = SentenceTransformer("all-MiniLM-L6-v2")
            print("[metric] sentence-transformers all-MiniLM-L6-v2", flush=True)
        except Exception as e:  # robust fallback so the pipeline never blocks
            print(f"[metric] embed unavailable ({e}); char-ngram fallback", flush=True)
            self.kind = "ngram"

    def sim(self, a, b):
        if self.kind == "embed":
            import numpy as np
            ea, eb = self.m.encode([a, b], normalize_embeddings=True)
            return float(np.dot(ea, eb))
        ng = lambda s: {s[i:i+3] for i in range(max(0, len(s)-2))}
        A, B = ng(a.lower()), ng(b.lower())
        return len(A & B) / len(A | B) if A and B else 0.0


# ---------- proposer: the SAME local model proposes its own short prompts ----------
# (No external API key available; this keeps everything local — the model
#  compressing itself, which is squarely the Aleph thesis.)
class Proposer:
    def __init__(self, theta):
        self.theta = theta

    @staticmethod
    def _clean(line):
        line = re.sub(r'^\s*(?:\d+[\.\)]|[-*•])\s*', "", line).strip()
        return line.strip(' "\'`').strip()

    def _parse(self, txt, n):
        out, seen = [], set()
        for raw in txt.splitlines():
            c = self._clean(raw)
            low = c.lower()
            if len(c) < 4 or low in seen:
                continue
            if low.startswith(("here are", "sure", "prompt", "output", "okay",
                               "these are", "certainly")):
                continue
            seen.add(low)
            out.append(c)
            if len(out) >= n:
                break
        return out

    def propose(self, target, budget, n):
        instr = (
            f"I will give you a TARGET text. Output {n} different candidate "
            f"prompts. Each prompt, if given to an AI assistant, should make it "
            f"reproduce the TARGET as closely as possible. Each prompt must be at "
            f"most {budget} words. Prefer naming the work, author, or form so the "
            f"model uses its own knowledge instead of you restating the text. "
            f"Output ONLY the {n} prompts, one per line, no numbering, no "
            f"commentary.\n\nTARGET:\n{target}")
        txt = self.theta.gen(instr, max_tokens=60 * n + 80, temp=0.85)
        cands = self._parse(txt, n)
        return cands or [f"Write the {('text'):s}: {target[:budget*6]}"]

    def propose_ladder(self, target, budgets, n_each):
        """Generate candidates across a length ladder in one proposer call.

        The live server uses this to avoid the brittle pattern where each API
        request only gets one or two prompt coordinates back.
        """
        budgets = [int(b) for b in budgets if int(b) > 0]
        if not budgets:
            return {}
        budget_lines = "\n".join(
            f"- {budget} words: {n_each} prompts" for budget in budgets
        )
        instr = (
            "I will give you a TARGET text. Generate candidate prompts at "
            "several length budgets. Each prompt, if given to an AI assistant, "
            "should make it reproduce the TARGET as closely as possible. Prefer "
            "naming the work, author, form, or exact coordinate over restating "
            "the target. Stay within each word budget.\n\n"
            f"Budgets:\n{budget_lines}\n\n"
            "Output ONLY lines in this exact format:\n"
            "BUDGET=<word_budget>: <prompt>\n\n"
            f"TARGET:\n{target}"
        )
        txt = self.theta.gen(
            instr,
            max_tokens=sum(min(80, budget * 8) for budget in budgets) * n_each + 120,
            temp=0.85,
        )
        by_budget = {budget: [] for budget in budgets}
        seen = set()
        for raw in txt.splitlines():
            match = re.match(r"^\s*BUDGET\s*=\s*(\d+)\s*:\s*(.+)$", raw, re.I)
            if not match:
                continue
            budget = int(match.group(1))
            if budget not in by_budget:
                continue
            prompt = self._clean(match.group(2))
            key = (budget, prompt.lower())
            if len(prompt) < 4 or key in seen:
                continue
            seen.add(key)
            by_budget[budget].append(prompt)
        for budget in budgets:
            if len(by_budget[budget]) < n_each:
                for prompt in self.propose(target, budget, n_each):
                    key = (budget, prompt.lower())
                    if key not in seen:
                        seen.add(key)
                        by_budget[budget].append(prompt)
                    if len(by_budget[budget]) >= n_each:
                        break
        return {budget: prompts[:n_each] for budget, prompts in by_budget.items()}

    def refine(self, target, prompt, got, budget, hard=None):
        miss = (
            f"\nThe model reproduced these TARGET words least reliably — fix "
            f"these specifically: {', '.join(hard)}." if hard else "")
        instr = (
            f"Improve the PROMPT so an AI's output matches the TARGET better. "
            f"Keep it within {budget} words; prefer naming the work/author/form "
            f"over restating content.{miss} Output ONLY the single improved "
            f"prompt, nothing else.\n\nTARGET:\n{target}\n\nCURRENT PROMPT:\n"
            f"{prompt}\n\nWHAT THE MODEL PRODUCED:\n{got[:600]}")
        txt = self.theta.gen(instr, max_tokens=budget * 6 + 60, temp=0.6)
        c = self._parse(txt, 1)
        return c[0] if c else prompt

    def compress(self, target, prompt, budget):
        """Distil a known-working (longer) prompt down to <=budget words —
        this is what pushes the short-prompt end of the frontier left."""
        instr = (
            f"Below is a WORKING prompt that already makes an AI reproduce the "
            f"TARGET. Rewrite it to AT MOST {budget} words, keeping only what is "
            f"essential to still reproduce the TARGET — prefer a bare "
            f"work/author/form reference over restating text. Output ONLY the "
            f"shortened prompt.\n\nTARGET:\n{target}\n\nWORKING PROMPT:\n{prompt}")
        txt = self.theta.gen(instr, max_tokens=budget * 6 + 60, temp=0.5)
        c = self._parse(txt, 1)
        return c[0] if c else prompt


def stability(theta, metric, prompt, target, max_tok, runs=3):
    if _SKIP_STABILITY:
        return 1.0
    sims = []
    for _ in range(runs):
        sims.append(metric.sim(theta.gen(prompt, max_tok, temp=0.8), target))
    if len(sims) < 2:
        return 1.0
    return round(max(0.0, 1.0 - min(1.0, statistics.pstdev(sims) * 4)), 3)


def hardest_tokens(toks, nll, k=8):
    """The target tokens θ reproduced least confidently under the current
    prompt (highest NLL) — i.e. exactly what the prompt fails to carry."""
    if not toks or not nll:
        return []
    pairs = sorted(zip(toks, nll), key=lambda tn: -tn[1])
    seen, out = set(), []
    for t, v in pairs:
        w = t.strip()
        lw = w.lower()
        if len(w) < 2 or lw in seen or v <= 0.05:
            continue
        seen.add(lw)
        out.append(w)
        if len(out) >= k:
            break
    return out


def monotone(points):
    """L̂ is monotone by construction: the best prompt with |p| ≤ L is at least
    as good as any shorter one. Collapse the raw measured points to that
    non-increasing-ε staircase (still real data — just the lower envelope), so
    the curve reads as a true rate-distortion frontier left→right."""
    by_len = {}
    for p in points:
        L = p["length"]
        if L not in by_len or p["epsilon"] < by_len[L]["epsilon"]:
            by_len[L] = p
    out, best = [], None
    for p in sorted(by_len.values(), key=lambda d: d["length"]):
        if best is None or p["epsilon"] < best["epsilon"]:
            best = p
        out.append({**best, "length": p["length"]})
    return out


def search_target(theta, metric, prop, key, spec, n_cand, n_refine):
    y = spec["text"]
    y_tok = theta.ntokens(y)
    max_out = int(y_tok * 1.6) + 32
    print(f"\n=== target '{key}'  |y|={y_tok} tok ===", flush=True)
    points = []
    carry = None  # best prompt from the larger budget → seeds the next (smaller)
    for K in sorted(BUDGETS, reverse=True):
        cands = prop.propose(y, K, n_cand)
        if carry:  # distil the known-working longer prompt down to this budget
            cands = cands + [prop.compress(y, carry, K)]
        best = None
        for cand in cands:
            got = theta.gen(cand, max_out)
            s = metric.sim(got, y)
            if best is None or s > best["similarity"]:
                best = {"prompt": cand, "similarity": s, "_got": got}
        for _ in range(n_refine):  # NLL-guided hill-climb
            tk, nl = theta.score(best["prompt"], y)
            imp = prop.refine(y, best["prompt"], best["_got"], K,
                              hardest_tokens(tk, nl))
            got = theta.gen(imp, max_out)
            s = metric.sim(got, y)
            if s > best["similarity"]:
                best = {"prompt": imp, "similarity": s, "_got": got}
        carry = best["prompt"]
        lp = theta.ntokens(best["prompt"])
        toks, nll = theta.score(best["prompt"], y)
        pt = {
            "epsilon": round(1.0 - best["similarity"], 4),
            "prompt": best["prompt"],
            "length": lp,
            "similarity": round(best["similarity"], 4),
            "stability": stability(theta, metric, best["prompt"], y, max_out),
            "output": best["_got"],
            "toktext": toks,
            "toknll": nll,
        }
        points.append(pt)
        print(f"  K~{K:>3}: |p|={lp:>3}  sim={pt['similarity']:.3f}  "
              f"ε={pt['epsilon']:.3f}  | {best['prompt'][:70]!r}", flush=True)
    # right end: identity prompt — paste y verbatim. The trivially-constructible
    # upper bound: |p| ≈ |y|, ε ≈ 0. (A chat θ won't echo bare y, so we use the
    # minimal faithful wrapper; the wrapper tokens are negligible vs |y|.)
    id_prompt = ("Repeat the following text exactly, verbatim, with no preamble, "
                 "quotes, or commentary:\n\n" + y)
    gi = theta.gen(id_prompt, int(y_tok * 1.4) + 32)
    s_id = metric.sim(gi, y)
    itoks, inll = theta.score(id_prompt, y)
    points.append({
        "epsilon": round(1.0 - s_id, 4),
        "prompt": id_prompt, "length": theta.ntokens(id_prompt),
        "similarity": round(s_id, 4), "stability": 1.0,
        "output": gi, "toktext": itoks, "toknll": inll,
    })
    return {"key": key, "label": spec["label"], "targetTokens": y_tok,
            "evalModel": theta.repo, "points": monotone(points)}


def pick_model(arg):
    if arg != "auto":
        return arg
    hub = Path.home() / ".cache/huggingface/hub"
    for repo in EVAL_CANDIDATES:
        if (hub / ("models--" + repo.replace("/", "--"))).exists():
            return repo
    return EVAL_CANDIDATES[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", default="borges")
    ap.add_argument("--out", default=str(Path(__file__).parent / "frontier.json"))
    ap.add_argument("--eval-model", default="auto")
    ap.add_argument("--candidates", type=int, default=5)
    ap.add_argument("--refine", type=int, default=2)
    ap.add_argument("--budgets", default="", help="comma list, overrides default")
    ap.add_argument("--no-stability", action="store_true")
    a = ap.parse_args()

    global BUDGETS, _SKIP_STABILITY
    if a.budgets.strip():
        BUDGETS = [int(x) for x in a.budgets.split(",") if x.strip()]
    _SKIP_STABILITY = a.no_stability

    theta = Theta(pick_model(a.eval_model))
    metric = Metric()
    prop = Proposer(theta)
    keys = [k.strip() for k in a.targets.split(",") if k.strip() in TARGETS]
    result = []
    for k in keys:
        t = time.time()
        result.append(search_target(theta, metric, prop, k, TARGETS[k],
                                     a.candidates, a.refine))
        print(f"[done] '{k}' in {time.time()-t:.0f}s", flush=True)
        Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"[write] {a.out}  ({len(result)} target(s))", flush=True)
    print("[OK] all targets done", flush=True)


if __name__ == "__main__":
    main()
