# Glossary

**Target output**: The text the user wants a model to reproduce or approximate.

**Prompt coordinate**: A prompt treated as a coordinate into a model's output space.

**Shortest found**: The shortest prompt discovered under the current model, decoding, metric, and budget.
It is not a proof of global optimality.

**Explicit reconstruction**: A baseline prompt that includes the target output directly, such as "reproduce this text".

**Leakage score**: A measure of how much target text appears directly in the prompt.

**Pareto frontier**: Candidate prompts that trade off prompt length, fit, stability, and leakage without being dominated.

**Token loss**: Per-token target loss or a fixture approximation of it.

**Inherent signal**: The part of the generated output that appears to be unfolded from model knowledge rather than copied from the prompt.
