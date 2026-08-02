"""NEO4J GRAPHRAG — the graph retrieval layer behind all three agents.

Dual-mode architecture (mirroring the project's mock-LLM philosophy):

    queries.py      The Cypher query library (real, portable Neo4j 5
                    syntax) + networkx implementations with IDENTICAL
                    semantics for offline fallback.
    store.py        Neo4jGraphStore (live driver + Cypher) and
                    LocalGraphStore (in-memory networkx). Same API,
                    same approval/curation governance.
    synthetic.py    Seeded generators for the fraud / cost / portfolio
                    graphs — realistic volume with planted ground truth
                    and distractors.
    investigator.py The RAG reader: turns an investigative assignment
                    into a plan of graph queries, executes them, and
                    composes a cited root-cause report (deterministic
                    mock planner; real-LLM seam marked).
"""
