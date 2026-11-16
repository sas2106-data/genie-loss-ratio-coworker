# Run evidence: end-to-end daily run

Readable, committed output of one real run of the `lrc_end_to_end` Lakeflow Job in a Databricks workspace
(synthetic data only). Regenerate with `python deploy/collect_run_evidence.py` after a run.

| | |
|---|---|
| Run | `604951087142024` · **SUCCESS** · 2026-11-16 03:45:28 UTC |
| Tasks | 9/9 succeeded (notebooks + Lakeflow pipeline + Lakebase) |
| Lakeflow expectations | 7 rule results recorded · 39 records failed a rule |
| Gen AI data-quality findings | 134 (ai_classify peril mismatch, ai_mask personal data), each explained by ai_query |
| Gen AI accuracy vs seeded defects | peril_mismatch (ai_classify): precision 0.447, recall 1.0; pii_in_free_text (ai_mask): precision 0.805, recall 1.0 |
| Rule-based findings | 19 (negative amounts, loss after report, non-EUR currency) |
| Reconciliation | Lakeflow gold incurred differs from original gold by **-2.99%** over 2026-10-18 → 2026-11-16 |
| Rate adequacy | 6 segment(s) where the achieved rate change is below the indicated rate change |
| Genie Agent benchmark | 10/10 questions answered correctly from the governed tables ([06_genie_agent.md](06_genie_agent.md)) |
| Lakebase actions | 16 actions in `ops.lr_actions` with team status |

| File | What it shows |
|---|---|
| [01_job_run.md](01_job_run.md) | Task graph, result and duration per task |
| [02_notebook_outputs.md](02_notebook_outputs.md) | Code and real output of every notebook task |
| [03_lakeflow_pipeline.md](03_lakeflow_pipeline.md) | Pipeline datasets and expectation pass/fail counts from the event log |
| [04_query_results.md](04_query_results.md) | DQ scorecard, Gen AI findings, reconciliation, rate adequacy, watchlist |
| [05_lakebase.md](05_lakebase.md) | Lakebase instance, synced table, Action Desk app, team status |
| [06_genie_agent.md](06_genie_agent.md) | Live Genie Agent answers: question, Genie's SQL, result, pass/fail |
| [csv/](csv/) | Query results as CSV |
