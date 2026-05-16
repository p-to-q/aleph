# Project Brief — Aleph

Aleph is a reverse prompt compression workbench.

## One-line definition

Given a target output, a fixed model, fixed decoding, fixed metric, and fixed search budget, Aleph searches for the shortest known prompt that can reproduce or approximate the target output and visualizes the compression path.

## User promise

Paste a target output, generate a path of candidate prompts, drag across the compression slider, and see how prompt length, target fit, stability, leakage, token loss, attribution, waveform, and eval results change.

## Developer promise

Every panel is driven by the same `AlephRun` contract. Fixture data, black-box observations, white-box observations, and future search adapters can evolve without rewriting the product around a new data shape.

## Product intent

Aleph is designed for two audiences:

- **Users** who want an immediate, visual understanding of how a target output can be compressed into a prompt coordinate.
- **Developers and researchers** who need clear data contracts, staged implementation, and honest labels for fixture, black-box, white-box, and simulated observations.

## Core interaction

The interface centers on a compression slider, but the slider is not the only interaction. Users can also select Pareto points, inspect token loss, compare prompt/output pairs, view waveform and attribution, and run evaluation checks.

## Constraint language

Every run must record:

- model theta;
- decoding strategy d;
- metric m;
- search budget B;
- leakage mode;
- observation mode.

## Non-goals

- No claim of absolute global shortest prompt.
- No hidden white-box claims without logits or model internals.
- No generic prompt-polishing workflow.
- No assumption that context-window length is the semantic right endpoint.
