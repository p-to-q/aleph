# Project Brief — Aleph

Aleph is a reverse prompt compression workbench.

## One-line definition

Given a target output and declared run conditions, Aleph searches for the shortest confirmed prompt
found in its observed archive and visualizes the path to explicit reconstruction. The oracle
coordinate length `L*` remains distinct from the run statistic `L_hat`.

## User promise

Paste a target output, generate a path of candidate prompts, drag across the compression slider, and
inspect prompt length, target fit, stability, the legacy surface-copy proxy, token loss, attribution,
waveform, and eval results. Paper-facing runs additionally preserve the typed PR0 evidence vector.

## Developer promise

Every panel is driven by the same `AlephRun` contract. Fixture data, black-box observations, white-box observations, and future search adapters can evolve without rewriting the product around a new data shape.

## Product intent

Aleph is designed for two audiences:

- **Users** who want an immediate, visual understanding of how a target output can be compressed into a prompt coordinate.
- **Developers and researchers** who need clear data contracts, staged implementation, and honest labels for fixture, black-box, white-box, and simulated observations.

## Core interaction

The interface centers on a compression slider, but the slider is not the only interaction. Users can also select Pareto points, inspect token loss, compare prompt/output pairs, view waveform and attribution, and run evaluation checks.

## Constraint language

Every current `AlephRun` must record:

- model theta;
- decoding strategy d;
- metric wire identifier (with a versioned manifest for paper-facing runs);
- search budget B;
- legacy `SearchConfig.mode` wire value (not scientific leakage evidence);
- observation mode.

A research-grade bundle additionally records the search algorithm/version, random state, exact model
and tokenizer revisions, append-only candidate/event archive, protected confirmation protocol, typed
metric/evidence manifest, and `ResourceLedger`.

## Non-goals

- No claim of absolute global shortest prompt.
- No hidden white-box claims without logits or model internals.
- No generic prompt-polishing workflow.
- No assumption that context-window length is the semantic right endpoint.
