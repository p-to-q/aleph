# Offline hosted-request shape audit — issue #107

The one-shot hosted policy is consumed. Do not create another task, call a model,
change the frozen experiment, or overwrite its evidence. This follow-up makes the
next admission decision reviewable without assuming an SDK preserves the
configured request.

## Acceptance gate

- Install the exact observed `kaggle-benchmarks==0.6.3` and `openai==3.16.2` in a
  separate optional environment; do not add them to product dependencies.
- Exercise the real ModelProxy factory, Aleph hosted adapter, and OpenAI request
  serializer through an in-memory HTTP transport. Capture only request bodies,
  never credentials or headers. Block socket connections before third-party
  imports and use an empty temporary home and credential-free environment.
- Check the target-description and empty-string discovery inputs plus the
  confirmation phase. Compare candidate text and requested decoding with actual
  JSON; reject a null-content substitution or disabled temperature control.
- Keep mocked response text explicit; report zero model calls and no provider
  acceptance, performance, cost, or scientific-validity claim. Do not label this
  macOS audit as a reproduction of the Linux hosted runtime.
- Retain a source/package-bound receipt, regression cases, and the exact offline
  command. A detected incompatibility is an expected blocked admission result,
  not a successful hosted experiment.

## Scope

Add a separate offline audit command, focused tests, evidence and runbook notes.
Do not alter `kaggle_canary.py`, the dated runner, original archive/policy, public
scores, historical HF artifacts, or model authorization. New provider-compatible
control and effective-decoding choices must be versioned before any fresh run.

## Observed result

The clean-source receipt blocks admission: empty text becomes null and requested
temperature zero becomes null. Three in-memory HTTP requests completed with mocked
responses; zero socket connections and zero model calls occurred. Relevant Kaggle
source hashes match the published 0.6.3 wheel. This also exposes an interpretation
gap in the old configuration-only decoding manifest: effective hosted temperature
was not captured and must remain unknown. No experiment, raw evidence, or dated
runner was rewritten.
