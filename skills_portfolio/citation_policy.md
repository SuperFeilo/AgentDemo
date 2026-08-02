# Skill: Citation Policy — Portfolio agent

Same as the cost agent's policy, retargeted for the journey:

1. Every number quoted in the final verdict must trace to a warehouse
   fact computed by a tool call (persistent_db) — never invented.
2. Every signal cited must have a lineage edge in the knowledge graph
   AND evidence that matches the observed stage outcome.
3. Every cited signal must carry provenance: at least one source memo
   referencing it (`data/portfolio_memos.json` → GraphRAG provenance).
4. Cite the corroborating stage agent's verdict next to the signal when
   present (corroboration strengthens the edge, it does not replace it).
5. "NO EDGE" is an honest answer when no signal clears weight AND
   direction — pretending is worse than admitting.