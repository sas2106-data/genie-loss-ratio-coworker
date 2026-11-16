# 03 · Lakeflow Spark Declarative Pipeline: `[LRC] Lakeflow ingest: raw volume → bronze → silver → Gen AI DQ → gold`

| | |
|---|---|
| Pipeline id | `6e420ed9-2d49-431b-b14e-b358b8d19ba9` |
| Source | [`src/pipeline/lrc_ingest_pipeline.sql`](../../src/pipeline/lrc_ingest_pipeline.sql) |
| Compute | serverless |
| Latest update | `b3bd8eb7-7cc2-4ae1-b234-6b8c1dc9c736` · **COMPLETED** · 2026-11-16T03:52:17.071Z |

## Datasets written in this update

| Dataset | Rows written |
|---|---|
| bronze_fnol |  |
| bronze_premium |  |
| dq_claims_issues | 153 |
| dq_daily_scorecard | 44 |
| gold_daily_loss_run_lf | 590 |
| gold_rate_adequacy | 20 |
| silver_claims | 3716 |
| silver_claims_ai_checked | 1981 |
| silver_premium | 590 |

## Expectations (data-quality rules) from the pipeline event log

| Dataset | Expectation | Passed | Failed |
|---|---|---|---|
| silver_claims | currency_is_eur | 3702 | 14 |
| silver_claims | has_claim_id | 3716 | 0 |
| silver_claims | loss_before_report | 3716 | 0 |
| silver_claims | non_negative_amount | 3701 | 15 |
| silver_claims | report_not_future | 3716 | 0 |
| silver_premium | currency_is_eur | 600 | 0 |
| silver_premium | positive_premium | 590 | 10 |
