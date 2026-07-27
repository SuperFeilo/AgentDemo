"""The analyst's data source: a tiny SQLite 'internal cost warehouse'.

Built deterministically from a seeded generator so the evals are
reproducible. The planted story (what the agent should discover):

  - auto_pd severity rises ~14% nationally (parts inflation + ADAS)
  - auto_bi severity rises fastest in the Northeast (medical inflation
    + litigation climate)
  - South auto frequency spikes in 2024Q3-Q4 (hurricane), then reverts
  - Midwest frequency blips in 2025Q1 (polar vortex) — a distractor
"""
from __future__ import annotations

import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "cost_warehouse.db"

QUARTERS = [f"{y}Q{q}" for y in (2023, 2024, 2025) for q in (1, 2, 3, 4)]
REGIONS = ["Northeast", "Midwest", "South", "West"]
COVERAGES = ["auto_pd", "auto_bi", "home"]
METRICS = ["severity", "frequency", "loss_ratio"]


def _generate() -> list[tuple]:
    rng = random.Random(42)
    rows = []

    def noise(pct: float = 0.008) -> float:
        return 1.0 + rng.gauss(0, pct)

    for region in REGIONS:
        # ── severity bases & quarterly growth per coverage ──────────
        sev_base = {"auto_pd": 4200.0,
                    "auto_bi": 15200.0 if region == "Northeast" else 14900.0,
                    "home": 9800.0}
        growth = {"auto_pd": 1.011,                                  # ~14%/12q
                  "auto_bi": 1.016 if region == "Northeast" else 1.008,
                  "home": 1.004}
        freq_base = {"auto_pd": 22.0, "auto_bi": 5.4, "home": 9.0}

        sev, freq = dict(sev_base), dict(freq_base)
        for q in QUARTERS:
            for cov in COVERAGES:
                sev[cov] *= growth[cov] * noise()
                freq[cov] *= 1.001 * noise(0.01)

                s, f = sev[cov], freq[cov]
                # planted events -------------------------------------
                if cov == "auto_pd" and region == "South" and q == "2024Q3":
                    f *= 1.18                      # hurricane
                if cov == "auto_pd" and region == "South" and q == "2024Q4":
                    f *= 1.10
                if cov == "auto_pd" and region == "Midwest" and q == "2025Q1":
                    f *= 1.06                      # polar vortex blip
                if cov == "home" and region == "South" and q == "2024Q3":
                    s *= 1.15                      # storm damage costs
                if cov == "home" and region == "South" and q == "2023Q3":
                    s *= 1.08

                rows.append((q, region, cov, "severity", round(s, 2)))
                rows.append((q, region, cov, "frequency", round(f, 3)))
                loss = 0.62 * (s / sev_base[cov]) ** 0.9 \
                    * (f / freq_base[cov]) ** 0.5 * noise(0.005)
                rows.append((q, region, cov, "loss_ratio", round(loss, 4)))
    return rows


def ensure_built() -> Path:
    """Create the warehouse DB on first use (idempotent)."""
    if DB_PATH.exists():
        return DB_PATH
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE fact_metric(
                       quarter TEXT, region TEXT, coverage TEXT,
                       metric TEXT, value REAL)""")
    con.executemany("INSERT INTO fact_metric VALUES (?,?,?,?,?)", _generate())
    con.commit()
    con.close()
    return DB_PATH


def connect() -> sqlite3.Connection:
    ensure_built()
    return sqlite3.connect(DB_PATH)
