# Skill: Verification (Reflection)

## When to use
Once — after all evidence is scored and before the decision step.
Andrew Ng's reflection pattern, made concrete: the agent re-examines
its own work before it is allowed to act on it.

## Tool
None. Verification runs against the case blackboard and the signals
already gathered.

## Checks
1. **Score arithmetic** — every signal carries its points `(+N)`; the
   running risk total must equal the sum of cited signals. A total
   without signals (or signals without points) means the reasoning
   broke somewhere. Fix: recompute from signals, correct the total,
   and record the correction.
2. **Threshold logic** — replay the review/escalation thresholds from
   `config/goal.yaml` against the (corrected) total and confirm the
   implied decision is the one about to be issued.

## Notes
- A clean self-check is the *expected* outcome — but the check is what
  makes the clean outcome trustworthy.
- Corrections are always reported, never silent.
