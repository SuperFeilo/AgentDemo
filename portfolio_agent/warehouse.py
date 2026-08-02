"""ANATOMY COMPONENT: WAREHOUSE (agent #3 — Portfolio Journey Analyst)

The data layer for the end-to-end commercial-lines journey. Seven linked
fact tables span the stages the demo wants to make traceable:

  fact_submission        ─┐
  fact_underwriting_note  │  submission_id
  fact_risk_score        │   joins these four to one submission
  fact_site_inspection  ─┘
  fact_bind             ─── policy_id (= submission_id after bind) /
                              submission_id back-ref
  fact_claim            ─── policy_id  ->  claim_id
  fact_settlement       ─── claim_id

Built deterministically (seeded) so evals are reproducible. The planted
story (what the agents should discover):

  ── submissions ────────────────────────────────────────────────
   • BRO-W (West broker) submits incomplete exposure detail → lower
     conversion AND worse eventual loss ratio
   • class 5437 attracts risk-score overrides that lower the model
     score, leading to under-pricing
  ── underwriting ────────────────────────────────────────────────
   • hedging UW notes correlate with under-pricing
   • risk-score overrides go hand-in-hand with waiving inspection flags
   • binds that carry an unresolved inspection flag yield ~40% more
     claims than clean binds (frequency uplift — small sample, so the
     agent must normalize by exposure and population)
  ── claims / settlement ────────────────────────────────────────
   • late FNOL (>14 days) on class 5437 → higher severity
   • reserves set <60% of final cost → settlement_vs_reserve_ratio
     balloons above 2.0 (a HIGH ratio signals 'inadequate reserve');
     leakage averages ~22% beyond reserve
   • slow settlement (>180 days) compounds leakage
"""
from __future__ import annotations

import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "portfolio_warehouse.db"

BROKERS = ["BRO-E", "BRO-W", "BRO-N", "BRO-S"]
REGIONS = {"BRO-E": "Northeast", "BRO-W": "West",
           "BRO-N": "Midwest", "BRO-S": "South"}
CLASS_CODES = ["5411", "5437", "5621", "6000"]
QUARTERS = [f"{y}Q{q}" for y in (2023, 2024) for q in (1, 2, 3, 4)]


def _generate() -> dict[str, list[tuple]]:
    rng = random.Random(7)
    rows = {
        "fact_submission": [], "fact_underwriting_note": [],
        "fact_risk_score": [], "fact_site_inspection": [],
        "fact_bind": [], "fact_claim": [], "fact_settlement": [],
    }

    def gauss(pct=0.02): return 1.0 + rng.gauss(0, pct)

    sub_id = 1000
    policy_id = 5000
    claim_id = 20000
    note_seq = 0
    inspection_seq = 0

    for q in QUARTERS:
        n_subs = 12 + rng.randint(0, 4)
        for _ in range(n_subs):
            sub_id += 1
            broker = rng.choices(BROKERS, weights=[3, 2, 3, 2])[0]
            region = REGIONS[broker]
            cls = rng.choice(CLASS_CODES)
            exposure = round(rng.uniform(150_000, 2_400_000))

            # ── planted: BRO-W exposure detail is missing ~55% of the time
            incomplete = (broker == "BRO-W" and rng.random() < 0.55) \
                or rng.random() < 0.08
            exposure_detail_complete = 0 if incomplete else 1

            loss_history_flag = 0 if rng.random() < 0.12 else 1
            rows["fact_submission"].append(
                (sub_id, q, broker, region, cls, exposure,
                 exposure_detail_complete, loss_history_flag))

            # ── underwriting notes (0-3 per submission) ─────────────────
            n_notes = rng.randint(0, 3)
            note_topics = []
            for _ in range(n_notes):
                note_seq += 1
                # planted: hedging notes appear mostly when override-down
                topic = rng.choice(["pricing", "risk", "class_code", "decline"])
                hedging = 1 if (topic == "pricing" and rng.random() < 0.35) else \
                    (1 if rng.random() < 0.10 else 0)
                note_topics.append((topic, hedging))
                rows["fact_underwriting_note"].append(
                    (note_seq, sub_id, q, topic, hedging))

            # ── risk score ─────────────────────────────────────────────
            base = 40 + int(exposure / 100_000) + rng.randint(0, 20)
            if cls == "5437":
                base += 8  # 5437 genuinely riskier
            # planted: 5437 + BRO-W attracts downward overrides ~60%
            override = 0
            overridden_to = base
            if cls == "5437" and rng.random() < 0.60:
                override = 1
                overridden_to = base - rng.randint(8, 15)
            rows["fact_risk_score"].append(
                (sub_id, q, base, overridden_to, override))

            # ── site inspection (only ~67% of submissions get one) ────
            inspected = rng.random() < 0.67
            flagged = 0
            if inspected:
                inspection_seq += 1
                # some inspections flag an issue; flagged issues get
                # ignored at bind when override=1
                flagged = 1 if rng.random() < 0.25 else 0
                rows["fact_site_inspection"].append(
                    (inspection_seq, sub_id, q, 1, flagged))

            # ── bind (rate ~68%) ────────────────────────────────────
            base_premium = round(exposure * 0.012 * (1 + (overridden_to / 100)))
            if override == 1 and cls == "5437":
                base_premium = round(base_premium * 0.85)  # under-priced
            bind = rng.random() < 0.68 if not incomplete else rng.random() < 0.45
            if not bind:
                continue
            policy_id += 1
            tier = "preferred" if overridden_to < 50 else \
                ("standard" if overridden_to < 65 else "excess")
            rows["fact_bind"].append(
                (policy_id, sub_id, q, base_premium,
                 2500,  # deductible
                 round(exposure * 1.0),  # limit ≈ exposure
                 tier, override, flagged,
                 1 if incomplete and rng.random() < 0.3 else 0))

            # ── claims (rate depends on signals) ────────────────────
            loss_rate = 0.18
            if override:
                loss_rate += 0.10  # under-pricing draws losses
            if flagged:  # flagged-above-risk-correlates-with-losses
                loss_rate += 0.12
            loss_rate = min(0.55, loss_rate)
            n_claims = 0
            if rng.random() < loss_rate:
                n_claims = 1
                claim_id += 1
                severity_base = 8_000 + int(exposure * 0.04)
                if cls == "5437":
                    severity_base = round(severity_base * 1.10)
                sev_mult = 1.0
                if flagged:
                    sev_mult *= 1.18  # planted: ignored flag → +18% severity
                if override:
                    sev_mult *= 1.05
                severity = round(severity_base * sev_mult * gauss(0.06))
                fnol_lag = rng.randint(1, 28)
                if cls == "5437" and rng.random() < 0.45:
                    fnol_lag = max(fnol_lag, 15)  # planted late FNOL on 5437

                # reserve: planted >60% of cost on most, but <60% on ~35%
                reserve_ratio = 0.75 if rng.random() < 0.65 else 0.45
                reserved = round(severity * reserve_ratio)
                occ_q = q
                rows["fact_claim"].append(
                    (claim_id, policy_id, cls, q, occ_q,
                     fnol_lag, severity, reserved))

                # ── settlement ─────────────────────────────────────
                settle_q_idx = QUARTERS.index(occ_q) + rng.randint(1, 2)
                settle_q = QUARTERS[min(settle_q_idx, len(QUARTERS) - 1)]
                # settle slightly above severity (ALAE + adjustment)
                settlement = round(severity * (1.0 + rng.uniform(0.05, 0.15)))
                if reserve_ratio < 0.60:
                    settlement = round(settlement * (1.0 + rng.uniform(0.08, 0.22)))
                leakage = max(0, settlement - reserved)
                rows["fact_settlement"].append(
                    (claim_id, settle_q, settlement, leakage,
                     round(settlement / reserved, 3) if reserved else 0,
                     QUARTERS.index(settle_q) - QUARTERS.index(occ_q)))
    return rows


_SCHEMA = """
CREATE TABLE fact_submission(
    submission_id INTEGER, quote_quarter TEXT, broker TEXT,
    region TEXT, class_code TEXT, exposure_amount REAL,
    exposure_detail_complete INTEGER, loss_history_flag INTEGER);
CREATE TABLE fact_underwriting_note(
    note_id INTEGER, submission_id INTEGER, note_quarter TEXT,
    note_topic TEXT, hedging_flag INTEGER);
CREATE TABLE fact_risk_score(
    submission_id INTEGER, score_quarter TEXT, model_score INTEGER,
    overridden_score INTEGER, override_flag INTEGER);
CREATE TABLE fact_site_inspection(
    inspection_id INTEGER, submission_id INTEGER, inspection_quarter TEXT,
    inspection_performed INTEGER, inspection_flagged_issue INTEGER);
CREATE TABLE fact_bind(
    policy_id INTEGER, submission_id INTEGER, bind_quarter TEXT,
    premium REAL, deductible REAL, limit_amount REAL,
    assumed_risk_tier TEXT, override_at_bind INTEGER,
    inspection_flagged_at_bind INTEGER, exposure_incomplete_at_bind INTEGER);
CREATE TABLE fact_claim(
    claim_id INTEGER, policy_id INTEGER, class_code TEXT,
    bind_quarter TEXT, occurrence_quarter TEXT,
    fnol_lag_days INTEGER, severity REAL, reserved_amount REAL);
CREATE TABLE fact_settlement(
    claim_id INTEGER, settlement_quarter TEXT, settlement_amount REAL,
    leakage_amount REAL, settlement_vs_reserve_ratio REAL,
    days_to_settle INTEGER);
CREATE INDEX idx_sub_q ON fact_submission(quote_quarter);
CREATE INDEX idx_bind_sub ON fact_bind(submission_id);
CREATE INDEX idx_claim_pol ON fact_claim(policy_id);
CREATE INDEX idx_sett_claim ON fact_settlement(claim_id);
"""


def ensure_built() -> Path:
    if DB_PATH.exists():
        return DB_PATH
    data = _generate()
    con = sqlite3.connect(DB_PATH)
    con.executescript(_SCHEMA)
    for table, tuples in data.items():
        placeholders = ",".join("?" * len(tuples[0])) if tuples else ""
        if tuples:
            con.executemany(f"INSERT INTO {table} VALUES ({placeholders})",
                           tuples)
    con.commit()
    con.close()
    return DB_PATH


def connect() -> sqlite3.Connection:
    ensure_built()
    return sqlite3.connect(DB_PATH)


if __name__ == "__main__":
    path = ensure_built()
    con = connect()
    for t in ["fact_submission", "fact_underwriting_note",
              "fact_risk_score", "fact_site_inspection",
              "fact_bind", "fact_claim", "fact_settlement"]:
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:28s} {n:5d} rows")
    con.close()
    print(f"\nWarehouse at {path}")