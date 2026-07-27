# Continuous Learning — design map

What "learning" means for an agent like this, what is **implemented**
in the project vs what a **production** version needs, and the
governance that makes it safe.

## The loop

```
            ┌──────────────┐     outcomes     ┌───────────────┐
            │  real world  │ ───────────────▶ │ outcome store │
            └──────────────┘                  └───────┬───────┘
                                                      │ replay decisions
                                                      ▼
┌──────────────┐   approve    ┌───────────────┐   propose   ┌───────────────┐
│    human     │ ◀─────────── │  proposals    │ ◀────────── │  analysis     │
└──────┬───────┘              └───────────────┘             └───────────────┘
       │ apply                        ▲
       ▼                              │ eval before/after
┌──────────────┐              ┌───────┴───────┐
│ skills/      │ ───────────▶ │     eval      │
│ weights as   │   measure    │  framework    │
│ data         │              └───────────────┘
└──────────────┘
```

## Implemented in this project (real code)

| Piece | Where | What it does |
|---|---|---|
| Outcome store | `data/outcomes.jsonl`, `data/outcomes_nextq.json` | Real-world results: SIU dispositions / next-quarter actuals |
| Analysis | `fraud_agent/learning.py`, `cost_agent/learning.py` | Per-signal precision (fraud); driver validation vs actuals (analyst) |
| Proposals | computed → dry-run by default | Halve noisy weights (fraud); reinforce/decay graph edges (analyst) |
| Human approval | 🎓 Learning tab + `--apply` flag | Nothing changes without a human gate |
| Weights as data | `config/fraud_weights.yaml`, graph edges in `data/cost_entities.json` | Brain/tools read them at run time |
| Before/after eval | Learning tab re-runs eval after apply | The delta is visible, not asserted |
| Reflection | `verification.md` skill + `reflect` plan step | Per-run self-check (Ng's pattern) — catches its own errors in-flight |

## Production would add

1. **Outcome capture at scale** — wired into claim-payment and SIU case
   systems, with arrival lag handling (fraud is confirmed months later;
   label delay must be part of the design).
2. **Drift monitoring** — per-signal precision *over time*, alerting
   when a signal degrades (fraud adapts; yesterday's weight decays).
3. **Richer updates** — not just weight nudges: new-signal proposals
   mined from confirmed cases, threshold tuning, and (for the LLM
   brains) prompt/skill-text revisions evaluated offline first.
4. **Shadow mode** — proposed weights run alongside production for N
   days; promotion requires shadow-eval superiority, not just a human
   nod.
5. **Rollback & lineage** — every weight versioned with its proposal,
   approver, and eval delta (git-like history for knowledge).
6. **Guarded metrics** — never optimize a single metric: track
   false-alarm rate on legit customers and investigator workload as
   constraints, not just precision/recall.

## Why the human gate stays (even in production)

Weights here change *decisions about people*: claims denied, cases
escalated, premiums priced. The same reasoning as the SIU autonomy gate
applies — the agent may propose, a human disposes, and the proposal
itself is auditable (which outcomes, which math, which delta). Learning
without this gate is how a feedback loop quietly becomes a liability.
