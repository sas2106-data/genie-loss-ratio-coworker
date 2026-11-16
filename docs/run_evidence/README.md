# Run evidence: end-to-end daily run

Readable, committed output of one real run of the `lrc_end_to_end` Lakeflow Job in a Databricks workspace
(synthetic data only). Regenerate with `python deploy/collect_run_evidence.py` after a run.

| | |
|---|---|
| Run | `485868090598415` · **SUCCESS** · 2026-11-16 05:05:29 UTC |
| Tasks | 11/11 succeeded (notebooks + Lakeflow pipeline + Lakebase) |
| Lakeflow expectations | 7 rule results recorded · 39 records failed a rule |
| Gen AI data-quality findings | 109 (ai_classify peril mismatch, ai_mask personal data), each explained by ai_query |
| Gen AI accuracy vs seeded defects | peril_mismatch (ai_classify): precision 0.913, recall 1.0; pii_in_free_text (ai_mask): precision 0.814, recall 1.0 |
| Rule-based findings | 19 (negative amounts, loss after report, non-EUR currency) |
| Reconciliation | Lakeflow gold incurred differs from original gold by **-2.99%** over 2026-10-18 → 2026-11-16 |
| Rate adequacy | 6 segment(s) where the achieved rate change is below the indicated rate change |
| Genie Agent benchmark | 10/10 questions answered correctly from the governed tables ([06_genie_agent.md](06_genie_agent.md)) |
| Lakebase actions | 16 actions in `ops.lr_actions` with team status |
| LLM judge of explanations | 40 explanations judged · avg score 3.51/5 · correct check 0.9 · no personal data 1.0 |
| Unity Catalog policies | 1 row filter(s) and 1 column mask(s) attached in Unity Catalog |
| ML forecast | UC model v2 scored 20 segments · 3 rising · 1 escalations (rising + Lakebase action OPEN) |

| File | What it shows |
|---|---|
| [01_job_run.md](01_job_run.md) | Task graph, result and duration per task |
| [02_notebook_outputs.md](02_notebook_outputs.md) | Code and real output of every notebook task |
| [03_lakeflow_pipeline.md](03_lakeflow_pipeline.md) | Pipeline datasets and expectation pass/fail counts from the event log |
| [04_query_results.md](04_query_results.md) | DQ scorecard, Gen AI findings, reconciliation, rate adequacy, watchlist |
| [05_lakebase.md](05_lakebase.md) | Lakebase instance, synced table, Action Desk app, team status |
| [07_genai_quality.md](07_genai_quality.md) | Gen AI precision/recall per check, history across runs, LLM-judge scores of the explanations |
| [08_governance.md](08_governance.md) | Unity Catalog row filter and column mask attached to the claims tables |
| [09_ml_forecast.md](09_ml_forecast.md) | Frequency forecast model in Unity Catalog, forecasts, escalations with Lakebase status |
| [notebooks/](notebooks/) | **Executed notebooks (.ipynb) with their real cell outputs**, one per job task |
| [job_run_log.txt](job_run_log.txt) | Plain-text job run log: every task, result, duration, dependencies |
| [pipeline_event_log.txt](pipeline_event_log.txt) | Plain-text Lakeflow pipeline event log for the run's update |
| [06_genie_agent.md](06_genie_agent.md) | Live Genie Agent answers: question, Genie's SQL, result, pass/fail |
| [csv/](csv/) | Query results as CSV |
