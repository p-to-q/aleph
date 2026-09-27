# Aleph

> **Aleph is a reverse prompt search engine.**
>
> Given a target output and declared run conditions, Aleph searches for the **shortest found prompt
> coordinates** that can reproduce or approximate the target, then visualizes the observed path from
> explicit reconstruction to compact coordinates. The search-independent oracle `L*` is a separate
> mathematical object; a finite run reports `L_hat`.

Read the full project thesis in [THESIS.md](THESIS.md).

**Live site:** [https://aleph.ptoq.io](https://aleph.ptoq.io)

## The image

> In Borges' image, the Aleph is a point in space that contains every other point.<br/>
> Seen from any angle, it reveals the universe at once: no overlap, no veil, no obstruction.<br/>
> In that tiny sphere, the narrator sees：

- the sea, dawn and dusk, and the crowds of the Americas
- a silver spiderweb at the center of a pyramid
- a shattered labyrinth — London
- every mirror in his bedroom
- grapes, snow, tobacco, metal, and steam in a California garden
- the red desert, and every grain of sand
- Beatriz Viterbo in Inverness, and the unreadable letter she wrote to Daneri
- his own face, his own inner body
- every word in the book now being read
- and everything else

Aleph adopts that image for model output space: a fixed model and decoding rule induce a
distribution over possible continuations, and a prompt is a coordinate that changes that
distribution.

a small place for seeing too much,<br/>
gently.

## What it is

- A target-output-first interface, not a prompt-polishing assistant.
- A compression slider over discrete Pareto candidate points.
- A workbench for prompt length, target fit, stability, token loss, attribution, and evals. The
  research contract distinguishes typed copy, recoverability, reference, provenance, and trace
  evidence; the current UI/run wire still exposes a legacy surface-copy scalar while that migration
  remains open.
- A repository shaped for human and agent continuation: clear thesis, visible artifact, receipts, limitations, and small reviewable changes.

## What it is not

- It does not prove a globally shortest prompt.
- It does not equate model-relative description length with strict Kolmogorov complexity.
- It does not claim white-box observations without logits or model internals.
- It does not treat context window length as the right endpoint of the slider.

## How we think about it

We started from a simple discomfort: prompt engineering is usually discussed as craft, taste, or folklore. You try a phrase, the model drifts, you try another phrase, and whatever works gets remembered as a trick. That is useful, but it hides the more interesting question:

If I already know the output I want, how little do I actually need to say to a fixed model before it can recover it?

That question pushed us away from "how do I write a better prompt?" and toward "what is the shortest usable prompt for this output inside this model?"

Aleph starts from one stubborn intuition: for a fixed model, a prompt is not only an instruction. It is also a coordinate into the model's library of possible continuations.

That flips the ordinary generation story:

```text
prompt p -> model M -> output y
```

into a search problem:

```text
given target y, fixed model theta, decoding d, metric m, and budget B
search for the shortest found prompt p
whose generated output is reliably close enough to y
```

What we are trying to define is not "the perfect prompt" in the abstract. The definition-level
object is model-relative but search-independent:

```text
rho(p; y, epsilon) =
  Pr_{Z ~ M_{theta,d}(. | p)}[m(Z, y) >= 1 - epsilon]

L*_{theta,d,m}(y; epsilon, beta) = min |p|
  over all prompts in the declared coordinate domain
  such that rho(p; y, epsilon) >= 1 - beta
```

For deterministic decoding, `rho` is a zero-or-one special case.

An actual Aleph run cannot assume that it found this oracle minimum. For searcher `A`, budget `B`,
and random state `omega`, it reports a separate found statistic:

```text
L_hat_{A,B,omega}(y; epsilon, beta) = min |p|
  over prompts actually observed by that run
  whose protected confirmation supports rho(p; y, epsilon) >= 1 - beta
```

The search budget belongs only to the second quantity. Conditional on the declared
simultaneous-coverage event, a protected-confirmed coordinate whose population reliability meets the
declared threshold constructively upper-bounds `L*`; the event's stated coverage controls the
confidence of that claim. This is not evidence that the global minimum was reached. Search-time point
estimates remain provisional.

An early practical scoring sketch compressed those concerns into one scalar:

```text
score(p) = fit(p, y) - lambda * length(p) - gamma * instability(p) - eta * leakage(p, y)
```

That formula is retained only as historical context. The governing
[PR0 research contract](docs/plans/iclr-readable-coordinate-program.md) supersedes an undocumented
composite score and a scalar `leakage` construct: scientific artifacts preserve a versioned metric
vector, typed provenance/recoverability channels, and the raw observations from which any explicitly
named scheduler or UI projection is derived. In plain language, we still want prompts that are
shorter, faithful, and stable, while distinguishing surface copying, recoverability, trace integrity,
and causal-source evidence instead of laundering them into one number.

That is also why the slider matters. We do not think Aleph is really about one magic prompt. We think it is about a **compression path**:

```text
Explicit Reconstruction
  -> descriptive prompt
  -> compressed concept prompt
  -> shortest found so far
```

So the current working beliefs behind Aleph are:

- We care more about the **path** than a single final prompt.
- We expect the frontier to be **discrete and Pareto-shaped**, not smooth.
- We treat **Shortest Found** as an honest left endpoint and **Explicit Reconstruction** as an honest right baseline.
- We treat typed provenance and recoverability evidence as part of the science, not a footnote: a
  surface-copy proxy, a reversible reconstruction test, search-trace integrity, and a causal-source
  intervention answer different questions.
- We expect multiple implementation routes to matter: hosted black-box loops, local white-box scoring, and later deeper search adapters.

We did not arrive at this in a vacuum. A few existing lines of work mattered a lot:

- [ACR / MiniPrompt](https://arxiv.org/abs/2404.15146) is the closest mandatory empirical neighbor:
  it already operationalizes target-first shortest-input compression with the model as decompressor.
- [Prompting Complexity](https://arxiv.org/abs/2607.06145) is the closest formal neighbor for
  fixed-model shortest plausible prompts.
- [ARCA / auditing-llms](https://github.com/ejones313/auditing-llms) remains a useful lower-level
  fixed-length raw-coordinate comparator, not Aleph's closest predecessor or product identity.
- [TextGrad](https://arxiv.org/abs/2406.07496) gave us a useful computational metaphor: even when the system is not differentiable end-to-end, you can still think in terms of gradient-like improvement over text.
- [llm-attacks / GCG](https://github.com/llm-attacks/llm-attacks) showed a more aggressive route through hard-prompt search. We take that seriously, but we do not want Aleph to inherit an attack-first identity by default.

That research pass led us to a practical decision: keep the product centered on a compression workbench, not on any single optimizer. Use the workbench to make the object legible first; then let different search routes compete behind the same run contract.

What we have actually done so far:

- We built the launch surface and slider-first interaction.
- We stabilized `AlephRun` as the shared run contract.
- We made fixtures, local MLX evidence traces, and hosted black-box runs coexist under one product language.
- We got far enough to know this is not just a metaphor, but not far enough to pretend the search problem is solved.

The next phase is to get more serious without getting more rigid.

Near-term research tracks:

- Clarify the workbench object: target output, candidate path, dashboard, evidence mode, and next action should read cleanly without docs.
- Implement the PR0 measurement contract: versioned fit/stability views, typed provenance and
  recoverability channels, explicit missingness, and named projections only where a scheduler or UI
  requires one.
- Keep both real-run routes visible: hosted black-box behavior and local white-box/MLX evidence should coexist without being conflated.
- Reproduce MiniPrompt/ACR as the mandatory closest empirical baseline, then compare lower-level
  ARCA/GCG raw-coordinate routes and other search adapters behind the same archive and evaluator
  boundary.
- Keep the repository file-first: runs, research notes, and future decisions should survive without chat history.

## Current status

Aleph is at `v1.0.3`: a small formal release of the active Next.js launch surface, shared `AlephRun` contract, fixture demos, local MLX evidence traces, a hosted black-box model adapter, and updated MLX runtime framing.

The release is intentionally honest about evidence:

- Precomputed examples are fixture-backed and labeled as such.
- `spring` and `crush` now include real local MLX token text / token NLL traces, but they are low-fit exploratory runs, not polished success demos.
- Hosted custom API runs call an external OpenAI-compatible model from the server side and return real candidate prompts and outputs as black-box observations.
- Hosted black-box runs do not expose logits or token NLL; token-loss panels only claim model-internal evidence when those fields are present.

## Repository map

```text
THESIS.md             Product and research thesis
web/                  Active Next.js launch surface
apps/web              Archived legacy/reference React/Vite console
apps/api              FastAPI orchestration layer (mock + local MLX search adapter)
search/               Local MLX live-search engine (Apple Silicon now; Linux CUDA upstream path)
packages/core         Shared AlephRun data contracts and scoring helpers
packages/ui           UI component shells for console panels
packages/fixtures     Sample runs used by the demo and checks
docs/                 Thesis support, strategy, architecture, research, UI, decisions, plans, verification
scripts/              Repository health checks that run without external installs
```

Start with [docs/contributor-map.md](docs/contributor-map.md) if you are joining the project.
[docs/state-of-play.md](docs/state-of-play.md) is the current confidence map, and
[docs/next-backlog.md](docs/next-backlog.md) owns implementation priority.
[docs/strategy.md](docs/strategy.md) preserves the historical product-shell and fallback rationale.

## Quick start

The repository is intentionally usable without private model credentials.

```bash
npm run lint
npm run test
npm --workspace web run build
```

For the current launch UI:

```bash
./start.sh
```

Open the printed localhost URL and choose a precomputed example, local MLX mode, or hosted custom API mode depending on the environment you have configured.

## Hosted API

The active web app exposes `POST /api/search` as an `AlephRun`-compatible adapter. It can run in three modes:

- `fixture`: precomputed runs from `web/public/aleph-frontier.json`.
- `hosted black-box`: server-side calls to an OpenAI-compatible `/chat/completions` endpoint.
- `local MLX`: optional MLX search service through `search/server.py`; Apple Silicon is the current maintainer route and Linux CUDA is the upstream expansion path.

Hosted API credentials must stay server-side. Do not use `NEXT_PUBLIC_` for API keys.

```bash
ALEPH_CUSTOM_API_BASE_URL=https://zapi.aicc0.com/v1
ALEPH_CUSTOM_API_MODEL=deepseek-v4-pro
ALEPH_CUSTOM_API_KEY=...
ALEPH_CUSTOM_API_FALLBACK_BASE_URL=https://jiuuij.de5.net/v1
ALEPH_CUSTOM_API_FALLBACK_MODEL=qwen3.6-27b-nothinking
ALEPH_CUSTOM_API_FALLBACK_KEY=...
```

The browser talks to the same-origin route by default:

```bash
NEXT_PUBLIC_CLAUDE_API=
```

Leave `NEXT_PUBLIC_SEARCH_API` unset unless you have a deployed or tunneled local-MLX-compatible service.

The static HTML prototype is available at:

```text
apps/web/static/aleph-atlas-console.html
```

## Completed launch phase

The first product-shell phase was file-first, UI-first, and adapter-honest. Its completed gates remain
useful fallbacks, but the current gate is a PR0-conformant replayable research run.

- [x] Ship a frontend-led console using fixtures and explicitly labeled observations.
- [x] Preserve the compression slider as the main interaction.
- [x] Make target input, current prompt, model output, Pareto frontier, token loss, search dial, waveform, attribution, exposure vectors, and eval suite work from one `AlephRun` contract.
- [x] Mark every mocked or simulated observation clearly.
- [x] Add a server-side hosted black-box API adapter for real prompt/output candidates.
- [x] Add real local MLX token traces for `spring` and `crush` fixtures.

## Research implementation horizon

The ordered, acceptance-gated version of this list lives in
[docs/next-backlog.md](docs/next-backlog.md).

- [x] Add a model-adapter API with hosted black-box and local MLX routes.
- [ ] Support repeated sampling, versioned metric vectors, typed provenance/recoverability evidence,
  and Pareto reranking without an undocumented composite.
- [ ] Add teacher-forced likelihood and token-level loss when logits are available.
- [ ] Add deletion ablation, prompt-token attribution, channel-qualified tested-noncopy modes, saved
  runs, and research reports; never promote a finite probe suite to universal non-leakage.
- [ ] Clarify the workbench object so target, candidate path, dashboard, evidence mode, and next action read cleanly without docs.
- [ ] Reproduce MiniPrompt/ACR as the mandatory closest baseline; keep ARCA/GCG as lower-level raw
  comparators and evaluate reflective/Pareto or soft-prompt routes as separately named adapters.
- [ ] Build a benchmark/report mode without letting Aleph collapse into just another leaderboard.
- [ ] Get accused, at least once, of reinventing Kolmogorov complexity for prompts; answer with receipts, caveats, and a cleaner run contract.

## Release gate

Before tagging a release, run:

```bash
npm run lint
npm run test
npm --workspace web run build
npm run api:smoke
apps/api/.venv/bin/python -m pytest apps/api/tests -q
search/.venv/bin/python search/preflight.py
git diff --check
```

For hosted deployments, also run a real `/health` and `/api/search` smoke with server-side API keys configured. The expected hosted observation mode is `black_box`.

## License

Apache-2.0.
