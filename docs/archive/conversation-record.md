# Conversation Record

This document preserves the project decisions and research framing from the Aleph design conversation.

## Initial brand decision

The name is **Aleph**. The symbol and wordmark share the same name.

## Product definition

Aleph is not "find any shortest prompt for any output." The stable definition is:

> Given a target output, a fixed model, a fixed decoding strategy, a fixed metric, and a fixed search budget,
> Aleph estimates the shortest known prompt that can reproduce or approximate the output and visualizes the
> compression path.

## Core metaphor

Borges' Library of Babel and Aleph image frame the product:

- the model output space is a finite token library;
- a prompt is a coordinate;
- a target output can be approached by moving between explicit reconstruction and compressed coordinate;
- the slider represents that path.

## UI decisions

Must have:

- target output input;
- current prompt;
- model output;
- main compression slider;
- Pareto frontier;
- dashboard metrics;
- token loss;
- loading/search dial;
- waveform;
- archive of design explorations.

Strongly recommended:

- loss curve;
- inherent signal;
- attribution score;
- exposure per vector;
- layer scan as future white-box mode;
- eval suite.

Defer:

- full mechanistic interpretability;
- soft prompt projection;
- production-grade ARCA/GCG integration;
- user accounts and persistence.

## Technical framing

- The left endpoint is **Shortest Found**, not a proof of theoretical optimum.
- The right endpoint is **Explicit Reconstruction**, not simply context-window length.
- Context window is physical capacity, not semantic boundary.
- Leakage score is required to distinguish compression from copying.
- White-box observations require real access to logits or model internals.

## Architecture decision

Adopt p-to-q style `standard + selected research`:

- public artifact and clear thesis;
- docs map;
- archive of decisions;
- small scripts;
- limited ADRs;
- no unused heavy process routes.

## Maintainer pass note

A later maintainer pass superseded the earlier `standard + selected research` phrasing. The repository now uses an artifact-first product-lab shape. The p-to-q seed remains a tone and discipline reference, but decisions and plans live under `docs/`, and `optional/` was removed to avoid template leftovers becoming confusing facts.
