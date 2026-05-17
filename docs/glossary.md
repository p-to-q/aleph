# Glossary — Aleph

**Target output**: The text the user wants a model to reproduce or approximate.

**Prompt coordinate**: A prompt treated as a coordinate into a model's output space.

**Shortest found**: The shortest prompt discovered under the current model, decoding, metric, and budget.
It is not a proof of global optimality.

**Explicit reconstruction**: A baseline prompt that includes the target output directly, such as "reproduce this text".

**AlephRun**: The shared run contract connecting a target output, search config, candidate points, selected candidate, and observations.

**Candidate point**: One prompt/output pair on a run's compression path, with metrics such as tokens, fit, stability, compression, and leakage.

**Leakage score**: A measure of how much target text appears directly in the prompt.

**Pareto frontier**: Candidate prompts that trade off prompt length, fit, stability, and leakage without being dominated.

**Observation mode**: The label that says whether observations are fixture, mock, simulated, black-box, or white-box.

**Non-leaking mode**: A run mode that treats copied target text as a constraint to avoid, while retaining explicit reconstruction as a leaky baseline.

**Token loss**: Per-token target loss or a fixture approximation of it.

**Inherent signal**: The part of the generated output that appears to be unfolded from model knowledge rather than copied from the prompt.

**Model-relative description length**: Aleph's budget-bounded estimate of how short a prompt can be for a fixed model, decoding rule, metric, and search procedure.
