"""ANATOMY COMPONENT: EVAL (1/3 — labeled dataset)

You cannot improve an agent you cannot measure. This is the ground
truth the agent is scored against: each claim labeled fraud or legit.
`flag_threshold` defines what counts as the agent "flagging" a claim:
any risk score >= threshold means the agent refused to auto-pay.
"""
LABELS = {
    "C-1001": "legit", "C-1002": "legit", "C-1003": "legit",
    "C-1004": "legit", "C-1009": "legit", "C-1010": "legit",
    "C-1013": "legit", "C-1014": "legit",
    "C-1005": "fraud",   # velocity: 4th claim in 4 months
    "C-1006": "fraud",   # ring: shares phone + shop with known fraud
    "C-1007": "fraud",   # notes: staged accident, contradictions
    "C-1008": "fraud",   # policy: 3 days old at $22k theft
    "C-1011": "fraud",   # ring + notes: guardrail crash story drifts
    "C-1012": "fraud",   # velocity + notes: 3rd theft claim, story changes
}
