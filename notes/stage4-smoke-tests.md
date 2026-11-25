# Stage 4 smoke tests (Nov 24, 2026)

Branch: pravesh/stage-4. Experiment id: 20261125T000324Z.

## What was checked
- The runner reads the bug list from bugs/core-set.txt. usd_per_cad = 0.70 (confirmed).
  Dry run: 50 units (10 bugs x 5 conditions x 1 trial).
- Fake LLM with the developer's fixed function: all 5 conditions PASS on call 1
  for luigi-25 and requests-3368. This was the first luigi bug run through the loop;
  its env_setup (pyenv step) works.
- Real trial of C0-C4 on luigi-25 and requests-3368: clue blocks appear exactly
  where expected. An empty clue gives the C1 prompt (luigi-25 C3 = C1), and C0 = C1.
- Windows (Command Prompt): dry run, and a luigi-25 C1/C2 run, both OK.
- No infrastructure problems.

## Clue check
```
[paste /tmp/clues.txt here]
```

## Per-condition averages and projection for 150 runs
```
[paste /tmp/summary.txt here]
```

## Status
Ready for the full run (10 bugs x 5 conditions x 3 trials) once Ankit says go.