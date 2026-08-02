# Skill: lineage_analysis  (agent #3 — Assembly / Reflection Analyst)

> Compose the journey: traverse the stage-flow lineage graph, rank
> predisposing signals, and identify the **high-leverage margin lever**.
> Verdict: `PROFIT EDGE IDENTIFIED` / `MARGINAL` / `NO EDGE`.

## When to act
After the three stage agents (submissions, underwriting, settlement)
have run for one subject segment. The assembly plan steps `stage_flow`,
`predisposing_signals`, `reflect`, `compose` use this skill.

## Workflow
1. **Stage funnel** — call `stage_flow` for the segment. Get the
   stage-by-stage retention/falloff rates. Quote them when composing.
2. **Candidate signals** — call `predisposing_signals` for the segment
   (filtered by region/class from the subject). Each edge:
   `signal PREDISPOSES outcome`, with weight/direction/lag.
3. **Reflect** — re-derive the funnel rate at each stage from the
   warehouse counts and re-screen candidates below the weight threshold.
4. **Compose** — claim profit edge only when the top signal has weight
   ≥ 0.55 *and* its direction agrees with the observed stage outcome.

## Margin thesis template
> *"{segment}: stage-flow drops most volume between {stageA} and
> {stageB} ({rate}). {topSignalName} (weight {w}, {direction}) drives
> {outcome}. Tracing this back through the journey: improvement at
> {leverageStage} is the high-leverage lever that lifts the
> contribution margin by an estimated {pct}."*

## What to cite
Every citation must carry:
- the lineage edge (`signal -> outcome`, weight, region/coverage)
- a warehouse figure measuring the magnitude
- the source memo via provenance
- the verdict from the matching stage agent (corroborating evidence)