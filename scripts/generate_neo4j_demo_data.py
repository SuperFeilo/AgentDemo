"""Regenerate the synthetic Neo4j GraphRAG demo data (seeded).

Usage:
    python scripts/generate_neo4j_demo_data.py [--seed N] [--size full|small]

Writes data/neo4j_*.json (graphs), data/neo4j_*_memos.json (source
documents) and data/neo4j_ground_truth.json (expected answers).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graphrag_neo4j.synthetic import generate_all

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=20260801)
    ap.add_argument("--size", choices=["full", "small"], default="full")
    args = ap.parse_args()
    files = generate_all(args.seed, args.size)
    for name, path in files.items():
        print(f"{name:16s} {path.name}  {path.stat().st_size:>8,} bytes")
    print("\nSynthetic Neo4j GraphRAG data regenerated.")
