# Stage 4 full run: experiment 20261126T212103Z

- Planned units: 150 (10 bugs x 5 conditions x 3 trials)
- Units with a result: 150
- Finished cleanly: yes; stopped by budget: no
- Outcomes: plausible 146, unsolved 4
- Infrastructure failures left after the rerun: 0
- Total cost: 0.0988 USD (0.1411 CAD of 50 CAD), seed 20261118
- Wall time: 2.64 hours of running

## Plausible fixes per condition (of all bugs x trials)

| Condition | Plausible | Runs | Rate | Avg calls | Avg cost USD |
|---|---|---|---|---|---|
| C0 | 30 | 30 | 100% | 2.03 | 0.00081 |
| C1 | 29 | 30 | 97% | 2.07 | 0.00086 |
| C2 | 29 | 30 | 97% | 1.67 | 0.00045 |
| C3 | 28 | 30 | 93% | 2.07 | 0.00078 |
| C4 | 30 | 30 | 100% | 1.37 | 0.00039 |

## Per bug: plausible / trials, and calls used (trial 1, 2, 3)

| Bug | C0 | C1 | C2 | C3 | C4 |
|---|---|---|---|---|---|
| requests-3368 | 3/3 (2,1,1) | 3/3 (1,2,2) | 3/3 (1,1,1) | 3/3 (1,1,1) | 3/3 (1,1,1) |
| luigi-25 | 3/3 (3,8,1) | 2/3 (2,10,5) | 3/3 (1,2,5) | 1/3 (2,10,10) | 3/3 (2,2,1) |
| luigi-3 | 3/3 (1,2,2) | 3/3 (2,1,2) | 3/3 (1,1,1) | 3/3 (1,4,1) | 3/3 (1,1,2) |
| requests-3390 | 3/3 (1,7,3) | 3/3 (4,3,3) | 2/3 (2,2,10) | 3/3 (2,3,4) | 3/3 (2,2,2) |
| requests-3179 | 3/3 (1,1,1) | 3/3 (1,1,1) | 3/3 (1,1,1) | 3/3 (1,1,1) | 3/3 (1,1,1) |
| luigi-14 | 3/3 (1,1,1) | 3/3 (2,1,1) | 3/3 (1,1,1) | 3/3 (1,1,1) | 3/3 (1,1,1) |
| luigi-22 | 3/3 (1,1,1) | 3/3 (1,1,1) | 3/3 (1,1,1) | 3/3 (1,2,1) | 3/3 (1,1,1) |
| luigi-4 | 3/3 (1,1,1) | 3/3 (1,2,2) | 3/3 (1,1,1) | 3/3 (1,1,1) | 3/3 (1,1,1) |
| luigi-26 | 3/3 (3,9,2) | 3/3 (1,2,2) | 3/3 (2,2,1) | 3/3 (1,2,2) | 3/3 (2,2,2) |
| requests-4723 | 3/3 (1,1,1) | 3/3 (1,2,2) | 3/3 (2,1,2) | 3/3 (2,1,1) | 3/3 (1,2,2) |

## Output of the summary script (python -m src.summarize, --bugs-n 10)

```
experiment 20261126T212103Z   bugs: requests-3368, luigi-25, luigi-3, requests-3390, requests-3179, luigi-14, luigi-22, luigi-4, luigi-26, requests-4723
cond  runs  plaus%  calls  wall s   llm s  test s   tok in  tok out   cost USD
------------------------------------------------------------------------------
C0      30     100    2.0    58.9     6.2    15.8      776     1241   0.000807
C1      30      97    2.1    58.5     6.9    14.4     1742     1325   0.000860
C2      30      97    1.7    75.0     3.7    17.8     1105      655   0.000449
C3      30      93    2.1    59.5     6.0    15.0     1629     1196   0.000782
C4      30     100    1.4    65.2     2.9    11.9      918      572   0.000394

Projection for 10 bugs x 3 trials x 5 conditions = 150 runs:
  cost  about 0.0988 USD = 0.1411 CAD (budget 50 CAD)
  time  about 2.6 hours of running
  These averages come from requests-3179 only if that is the only bug run; harder bugs need more calls.
Saved results\experiments\20261126T212103Z\summary.json
```
