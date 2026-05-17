# Handoff

Use this folder when work spans multiple contributors or agents. A handoff should include:

- account or role;
- objective;
- files touched;
- validation run;
- source mode (`fixture`, `mock`, `black_box`, `white_box`, or `simulated`);
- evidence or command receipt for any real model/runtime claim;
- remaining risks;
- next action.

Do not use handoff notes to create a second product contract. If a handoff needs
a new field, enum, endpoint, or theory claim, route it through Account A and the
active docs before another account depends on it.

## Live Search Receipt

When Account B verifies `local_mlx_search` against a running `search/server.py`,
paste the receipt block emitted by:

```bash
npm run api:live-smoke
```

The receipt must include:

- command and date;
- model;
- source/observation mode;
- candidate count;
- selected candidate id;
- whether token NLL was present;
- exactly which claim is supported and which claims are not supported.
