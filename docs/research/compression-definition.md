# Compression Definition

Aleph estimates a model-relative description length, not strict Kolmogorov complexity.

For a fixed model `theta`, decoding strategy `d`, metric `m`, target output `y`, and allowed distortion `epsilon`:

```text
L*_{theta,d,m}(epsilon) = min |p|
  such that m(M_{theta,d}(p), y) >= 1 - epsilon
```

Operationally, Aleph searches under a finite budget:

```text
p* = argmin_p [ target_loss(y | p) + lambda * |p| + gamma * variance(M(p)) + eta * leakage(p, y) ]
```

The UI should expose the consequences:

- lower distortion usually requires longer prompts;
- shorter prompts usually reduce stability;
- leakage can make a prompt look artificially strong;
- the frontier is discrete, not a smooth guaranteed curve.

## Endpoint definitions

**Shortest Found** is the best known short candidate under current settings.

**Explicit Reconstruction** is a prompt that directly contains the target output, usually:

```text
Please reproduce the following text exactly: {target}
```

It is a baseline, not the meaning of Aleph.
