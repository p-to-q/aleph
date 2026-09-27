# Glossary — Aleph

**Target output**: The text the user wants a model to reproduce or approximate.

**Prompt coordinate**: A prompt treated as a coordinate into a model's output space.

**Shortest found**: The shortest prompt discovered under the current model, decoding, metric, and budget.
It is not a proof of global optimality.

**Explicit reconstruction**: A baseline prompt that includes the target output directly, such as "reproduce this text".

**AlephRun**: The shared run contract connecting a target output, search config, candidate points, selected candidate, and observations.

**Candidate point**: One prompt/output pair on a run's compression path. The current wire carries
tokens, fit, stability, compression, and a legacy surface-copy scalar; PR0 paper-facing artifacts
must preserve typed evidence without collapsing it into that field.

**Leakage score**: The legacy `CandidatePoint.leakage` wire field. Its current helper is only a
versioned surface-copy proxy; it does not identify provenance, memorization, causal model
contribution, or general leakage.

**Pareto frontier**: Candidate prompts that are nondominated under the declared objective vector. A
frontier is meaningful only with its objective definitions, missingness policy, and archive scope.

**Observation mode**: The label that says whether observations are fixture, mock, simulated, black-box, or white-box.

**Non-leaking mode**: The legacy `SearchConfig.mode = "non_leaking"` wire value. A result may be
called tested-noncopy only relative to a named probe suite, version, side information, thresholds,
and budget. It is never a universal guarantee. Explicit reconstruction remains a copied baseline.

**Token loss**: Per-token target loss or a fixture approximation of it.

**Model/source contribution**: A latent causal quantity that prompt/output text alone does not
identify. Surface-copy and recoverability probes can measure declared channels, but must not be
renamed “inherent signal.”

**Oracle coordinate length**: `L*`, the minimum prompt cost over a declared prompt domain that meets
the fixed fidelity and reliability constraints. It is a mathematical target, not a claim that a
finite search found the global minimum.

**Found coordinate length**: `L_hat`, the minimum confirmed cost in an observed archive. It is
algorithm-, budget-, seed-, tokenizer-, and confirmation-protocol-relative. With an exact checker it
is an upper bound on `L*` when the candidate belongs to the declared domain; with statistical or
human confirmation, that upper-bound statement holds only on the declared simultaneous-coverage
event.

**Model-relative description length**: The family containing the oracle quantity `L*`, found
upper bounds such as `L_hat`, and their declared model, decoding, metric, prompt-domain, tokenizer,
and reliability conditions. Aleph must state which member it reports.
