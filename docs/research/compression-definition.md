# Compression Definition

Aleph defines a model-relative description-length object and measures algorithm-conditioned
shortest-found upper bounds. It does not estimate strict Kolmogorov complexity.

For a fixed model `theta`, decoding strategy `d`, metric `m`, target output `y`, and allowed distortion `epsilon`:

```text
rho(p; y, epsilon) =
  Pr_{Z ~ M_{theta,d}(. | p)}[m(Z, y) >= 1 - epsilon]

L*_{theta,d,m}(y; epsilon, beta) = min |p|
  over all prompts in the declared coordinate domain
  such that rho(p; y, epsilon) >= 1 - beta
```

For deterministic decoding, `rho` is a zero-or-one special case.

Operationally, searcher `A` observes only a budget- and random-state-dependent archive:

```text
L_hat_{A,B,omega}(y; epsilon, beta) = min |p|
  over prompts actually observed by that run
  whose protected confirmation supports rho(p; y, epsilon) >= 1 - beta
```

The search budget belongs to `L_hat`, not `L*`. Unless the coordinate domain is exhausted or a
sound cheaper-prefix certificate is available, the confirmed shortest-found value constructively
upper-bounds `L*` only conditional on the declared simultaneous-coverage event; the event's stated
coverage controls the confidence of that claim. Search-time point estimates remain provisional.
Scientific artifacts preserve a versioned metric vector and raw
observations. A separately named optimizer or UI projection may use a scalar rule, but it does not
replace the multidimensional record or define the research construct.

In white-box settings, `target_loss(y | p)` may be teacher-forced NLL or a related model-internal
likelihood score. In black-box settings, NLL remains `unknown` or absent; generated outputs support
separately named empirical fidelity and reliability metrics, not an approximation silently relabeled
as model-internal likelihood.

The UI should expose the consequences:

- lower distortion usually requires longer prompts;
- shorter prompts usually reduce stability;
- surface copying, recoverable encoding, trace contamination, and source evidence can make a prompt
  look strong for different reasons and must remain typed separately;
- the frontier is discrete, not a smooth guaranteed curve.

## Endpoint definitions

**Shortest Found** is the best known short candidate under current settings.

**Explicit Reconstruction** is a prompt that directly contains the target output, usually:

```text
Please reproduce the following text exactly: {target}
```

It is a baseline, not the meaning of Aleph.

## Adjacent endpoint language

The slider can gesture toward two larger conceptual regions without turning them into false evidence:

- left of **Shortest Found** sits an unknown compression zone, sometimes described as moving toward an Aleph limit or model-relative lower bound;
- right of **Explicit Reconstruction** sits a redundancy/context-wall zone, where more tokens may still fit but add little semantic necessity.

These regions are explanatory language for the workbench, not verified candidate points.
