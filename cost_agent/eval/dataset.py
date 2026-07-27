"""ANATOMY COMPONENT: EVAL (agent #2, 1/3 — ground truth)

Evaluating an *analyst* agent is different from evaluating a
classifier. Here ground truth has three parts per question:
  - required_drivers: must be cited (recall)
  - acceptable_drivers: may be cited without penalty (precision)
  - numeric_truth: computed live from the warehouse, so the eval can
    never drift out of sync with the data
"""
QUESTIONS = [
    {
        "id": "Q1",
        "text": "Why is national auto physical-damage severity trending up?",
        "metric": "severity", "region": "ALL", "coverage": "auto_pd",
        "pattern": "sustained",
        "required_drivers": ["parts_inflation", "adas_complexity"],
        "acceptable_drivers": ["supply_chain"],
        "numeric_field": "cumulative_pct", "tolerance": 1.0,
    },
    {
        "id": "Q2",
        "text": "What is driving Northeast auto bodily-injury severity?",
        "metric": "severity", "region": "Northeast", "coverage": "auto_bi",
        "pattern": "sustained",
        "required_drivers": ["medical_inflation", "litigation_climate"],
        "acceptable_drivers": [],
        "numeric_field": "cumulative_pct", "tolerance": 1.0,
    },
    {
        "id": "Q3",
        "text": "Why did South auto claim frequency spike in late 2024?",
        "metric": "frequency", "region": "South", "coverage": "auto_pd",
        "pattern": "episodic",
        "required_drivers": ["cat_weather"],
        "acceptable_drivers": ["vmt_mileage"],
        "numeric_field": "peak_dev_pct", "tolerance": 2.0,
    },
]
