# 02 · Notebook outputs (captured from the job run)

Each section is one notebook task: the code that ran and the output it printed or displayed. Markdown cells and setup cells without output are omitted.


## Task `governance_policies` · `src/governance/05_row_filter_column_mask`


**Cell** `spark.sql(f"""`

| group_name | region |
|---|---|
| lrc_claims_uk | UK & Ireland |
| lrc_claims_france | France |
| lrc_claims_dach | DACH |
| lrc_claims_southern_europe | Southern Europe |
| lrc_claims_benelux | Benelux |
| lrc_claims_all | UK & Ireland |
| lrc_claims_all | France |
| lrc_claims_all | DACH |
| lrc_claims_all | Southern Europe |
| lrc_claims_all | Benelux |

**Cell** `spark.sql(f"""`

```text
policy functions ready
```

**Cell** `if spark.catalog.tableExists(f"{CATALOG}.{SCHEMA}.silver_claims"):`

| claim_id | region | seen_by_pii_readers | seen_by_everyone_else |
|---|---|---|---|
| CLM-3073814 | UK & Ireland | Burst pipe on the third floor caused water damage to offices below in Dublin. Contact Anna Becker on +44 7700 549807 or anna@example.com | Burst pipe on the third floor caused water damage to offices below in Dublin. Contact [name] on [phone] or [email] |
| CLM-3073822 | Benelux | Heavy seas caused containers to shift and fall overboard en route to Antwerp. Contact Sophie Martin on +44 7700 839104 or sophie@example.com | Heavy seas caused containers to shift and fall overboard en route to Antwerp. Contact [name] on [phone] or [email] |
| CLM-3073903 | Benelux | Delivery van rear-ended at traffic lights in Rotterdam, bumper and tailgate damaged. Contact Sophie Martin on +44 7700 253185 or sophie@example.com | Delivery van rear-ended at traffic lights in Rotterdam, bumper and tailgate damaged. Contact [name] on [phone] or [email] |
| CLM-3073906 | UK & Ireland | Company car collided with a parked vehicle while reversing in Dublin. Contact Carlos Ruiz on +44 7700 127259 or carlos@example.com | Company car collided with a parked vehicle while reversing in Dublin. Contact [name] on [phone] or [email] |
| CLM-3073908 | UK & Ireland | Container seal broken, part of the cargo missing on arrival in Dublin. Contact Luca Rossi on +44 7700 510172 or luca@example.com | Container seal broken, part of the cargo missing on arrival in Dublin. Contact [name] on [phone] or [email] |
| CLM-3073912 | Southern Europe | River flooding entered the ground floor of the Milan depot, water 40cm deep. Contact Carlos Ruiz on +44 7700 379512 or carlos@example.com | River flooding entered the ground floor of the Milan depot, water 40cm deep. Contact [name] on [phone] or [email] |
| CLM-3073963 | Southern Europe | Pedestrian injured when our delivery vehicle mounted the kerb in Porto. Contact Carlos Ruiz on +44 7700 408047 or carlos@example.com | Pedestrian injured when our delivery vehicle mounted the kerb in Porto. Contact [name] on [phone] or [email] |
| CLM-3073978 | Southern Europe | Pallets crushed during loading, consignment for Milan rejected. Contact James O'Brien on +44 7700 859887 or james@example.com | Pallets crushed during loading, consignment for Milan rejected. Contact [name] on [phone] or [email] |
| group_name | claims_visible |
|---|---|
| lrc_claims_all | 3716 |
| lrc_claims_benelux | 400 |
| lrc_claims_dach | 1020 |
| lrc_claims_france | 679 |
| lrc_claims_southern_europe | 617 |
| lrc_claims_uk | 1000 |

**Cell** `for t in ["silver_claims", "silver_claims_ai_checked"]:`

```text
silver_claims [('Row Filter', '`<catalog>`.`loss_ratio_coworker`.`lrc_region_filter` ON (region)'), ('# Column Masks', '')]
silver_claims_ai_checked (policies are attached when the pipeline next refreshes)
```

## Task `generate_loss_run` · `src/setup/01_generate_loss_run`


**Cell** `dbutils.widgets.text("catalog", "")`

```text
Target: <catalog>.loss_ratio_coworker
```

**Cell** `def write(df, name, comment):`

```text
wrote policies                150,000 rows
wrote claims                   77,527 rows
wrote earned_premium_daily     13,700 rows

As of 2026-11-16: book loss ratio 63.3% | 77,527 claims | seeded events: 238 hail, 120 motor, 1 large BI
```

## Task `lakebase_setup` · `src/lakebase/01_setup_lakebase`


**Cell** `inst = ensure_instance(INSTANCE)`

```text
Lakebase instance lrc-lakebase · host ep-wispy-pine-d2mlyr2v.database.us-east-1.cloud.databricks.com · database lrc_ops
schemas ops, pricing and tables ready
```

**Cell** `import numpy as np`

```text
pricing.quotes already has 24,300 rows
ops.lr_actions 16
pricing.quotes 24300
pricing.rate_actions 2
```

## Task `land_raw_files` · `src/raw/03_land_raw_files`


**Cell** `dbutils.widgets.text("catalog", "")`

```text
Landing into /Volumes/<catalog>/loss_ratio_coworker/raw
```

**Cell** `def clean_dir(path):`

```text
Landed 30 days (2026-10-18 → 2026-11-16) into /Volumes/<catalog>/loss_ratio_coworker/raw
{
 "claims": 3750,
 "premium_rows": 600,
 "mismatch": 42,
 "pii": 137,
 "neg": 15,
 "dates": 7,
 "dupes": 34,
 "ccy": 14
}
```

## Task `semantic_layer` · `src/setup/02_semantic_layer`


**Cell** `display(spark.sql("SELECT line_of_business, region, status, primary_driver, ROUND(lr_7d,3) lr_7d, ROUND(lr_30d,3) lr_30d`

| line_of_business | region | status | primary_driver | lr_7d | lr_30d | target_loss_ratio | gap_7d_pts |
|---|---|---|---|---|---|---|---|
| Property | DACH | RED | Catastrophe event | 2.659 | 0.981 | 0.6 | 205.9 |
| Liability | Southern Europe | RED | Large loss | 2.09 | 0.94 | 0.66 | 143.0 |
| Motor | UK & Ireland | RED | Frequency | 1.035 | 0.841 | 0.7 | 33.5 |
| Liability | UK & Ireland | AMBER | Within normal variation | 0.795 | 0.666 | 0.66 | 13.5 |
| Property | UK & Ireland | AMBER | Within normal variation | 0.728 | 0.593 | 0.6 | 12.8 |
| Liability | France | AMBER | Frequency | 0.768 | 0.584 | 0.66 | 10.8 |
| Marine | France | GREEN | Within normal variation | 0.619 | 0.525 | 0.57 | 4.9 |
| Property | Benelux | GREEN | Within normal variation | 0.627 | 0.495 | 0.6 | 2.7 |
| Marine | DACH | GREEN | Within normal variation | 0.568 | 0.674 | 0.57 | -0.2 |
| Motor | Benelux | GREEN | Within normal variation | 0.697 | 0.699 | 0.7 | -0.3 |
| Marine | UK & Ireland | GREEN | Within normal variation | 0.535 | 0.609 | 0.57 | -3.5 |
| Motor | Southern Europe | GREEN | Within normal variation | 0.656 | 0.752 | 0.7 | -4.4 |
| Motor | DACH | GREEN | Within normal variation | 0.625 | 0.713 | 0.7 | -7.5 |
| Liability | DACH | GREEN | Within normal variation | 0.542 | 0.674 | 0.66 | -11.8 |
| Marine | Southern Europe | GREEN | Within normal variation | 0.434 | 0.451 | 0.57 | -13.6 |
| Liability | Benelux | GREEN | Within normal variation | 0.521 | 0.569 | 0.66 | -13.9 |
| Marine | Benelux | GREEN | Severity | 0.43 | 0.441 | 0.57 | -14.0 |
| Property | Southern Europe | GREEN | Within normal variation | 0.45 | 0.584 | 0.6 | -15.0 |
| Motor | France | GREEN | Within normal variation | 0.549 | 0.679 | 0.7 | -15.1 |
| Property | France | GREEN | Within normal variation | 0.419 | 0.556 | 0.6 | -18.1 |

## Task `watch_and_explain` · `src/jobs/daily_loss_ratio_watch`


**Cell** `watch = spark.sql(f"""`

```text
6 segments need attention | book YTD LR 63.6%, COR 92.1% vs industry 92.9%
```
| line_of_business | region | owner_team | as_of_date | target_loss_ratio | amber_pts | red_pts | lr_7d | lr_30d | lr_ytd | freq_7d | freq_base | sev_7d | sev_base | large_losses_7d | cat_share_7d | incurred_7d | gap_7d_pts | gap_30d_pts | freq_change | sev_change | primary_driver | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Property | DACH | Property Underwriting | 2026-11-16 | 0.6 | 10.0 | 25.0 | 2.6593116321170864 | 0.9810150961485058 | 0.6589842631991109 | 61.18764803764787 | 9.87173589452217 | 43461.576272401435 | 58994.76312080538 | 0 | 0.8310380810824852 | 12125779.78 | 205.9 | 38.1 | 5.198 | -0.263 | Catastrophe event | RED |
| Liability | Southern Europe | Casualty Underwriting | 2026-11-16 | 0.66 | 10.0 | 25.0 | 2.0897577713813615 | 0.9401509447041853 | 0.6953967964638149 | 9.804896189474686 | 9.427890889819096 | 213134.1047368421 | 68337.16806584361 | 3 | 0.0 | 4049547.9899999998 | 143.0 | 28.0 | 0.04 | 2.119 | Large loss | RED |
| Motor | UK & Ireland | Motor Underwriting | 2026-11-16 | 0.7 | 8.0 | 20.0 | 1.0351407816835614 | 0.8408605666612735 | 0.7166413021377629 | 50.09747518480893 | 38.20985347860525 | 20662.533947368418 | 19236.146901041666 | 0 | 0.0 | 3140705.1599999997 | 33.5 | 14.1 | 0.311 | 0.074 | Frequency | RED |
| Liability | UK & Ireland | Casualty Underwriting | 2026-11-16 | 0.66 | 10.0 | 25.0 | 0.7945636047723654 | 0.6662629069861268 | 0.6989768635385595 | 11.031849800895216 | 9.846168375226322 | 72024.51258064517 | 74662.4911764706 | 1 | 0.0 | 2232759.89 | 13.5 | 0.6 | 0.12 | -0.035 | Within normal variation | AMBER |
| Property | UK & Ireland | Property Underwriting | 2026-11-16 | 0.6 | 10.0 | 25.0 | 0.7282354841240234 | 0.5929742840625615 | 0.5901111262696466 | 11.489493093775177 | 9.961729376821383 | 63382.73396226416 | 57064.144311183154 | 1 | 0.0 | 3359284.9000000004 | 12.8 | -0.7 | 0.153 | 0.111 | Within normal variation | AMBER |
| Liability | France | Casualty Underwriting | 2026-11-16 | 0.66 | 10.0 | 25.0 | 0.7677543674222962 | 0.5835748427629629 | 0.6320859784372923 | 13.43314073743711 | 10.698533409745693 | 57153.75 | 62068.2673421927 | 0 | 0.0 | 1600305.0 | 10.8 | -7.6 | 0.256 | -0.079 | Frequency | AMBER |

**Cell** `import pandas as pd`

```text
recorded 6 alerts and 16 actions
```

**Cell** `import json, requests`

```text
[slack dry-run] LR-20261116-PRO-DACH
{"text": "Loss ratio RED: Property / DACH", "blocks": [{"type": "header", "text": {"type": "plain_text", "text": "Loss ratio alert: Property, DACH"}}, {"type": "section", "fields": [{"type": "mrkdwn", "text": "*Status*\n:red_circle: RED"}, {"type": "mrkdwn", "text": "*Driver*\nCatastrophe event"}, {"type": "mrkdwn", "text": "*7-day LR*\n266% vs target 60% (+206 pts)"}, {"type": "mrkdwn", "text": "*30-day LR*\n98%"}]}, {"type": "section", "text": {"type": "mrkdwn", "text": "*Why (Genie)*\n- **Property DACH loss ratio rose to 265.9%**, up **219.6 percentage points** from **46.3%** in the prior 7...

[teams dry-run] LR-20261116-PRO-DACH
{"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.4", "body": [{"type": "TextBlock", "size": "Large", "weight": "Bolder", "text": "Loss ratio RED: Property, DACH", "color": "Attention"}, {"type": "FactSet", "facts": [{"title": "Driver", "value": "Catastrophe event"}, {"title": "7-day LR", "value": "266% (target 60%, +206 pts)"}, {"title": "30-day LR", "value": "98%"}, {"title": "Alert", "value": "LR-20261116-PRO-DACH"}]}, {"type": "Text...

[slack dry-run] LR-20261116-LIA-SOUT
{"text": "Loss ratio RED: Liability / Southern Europe", "blocks": [{"type": "header", "text": {"type": "plain_text", "text": "Loss ratio alert: Liability, Southern Europe"}}, {"type": "section", "fields": [{"type": "mrkdwn", "text": "*Status*\n:red_circle: RED"}, {"type": "mrkdwn", "text": "*Driver*\nLarge loss"}, {"type": "mrkdwn", "text": "*7-day LR*\n209% vs target 66% (+143 pts)"}, {"type": "mrkdwn", "text": "*30-day LR*\n94%"}]}, {"type": "section", "text": {"type": "mrkdwn", "text": "*Why (Genie)*\n- **Liability in Southern Europe is at 209.0%**, which is **143.0 percentage points above*...

[teams dry-run] LR-20261116-LIA-SOUT
{"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.4", "body": [{"type": "TextBlock", "size": "Large", "weight": "Bolder", "text": "Loss ratio RED: Liability, Southern Europe", "color": "Attention"}, {"type": "FactSet", "facts": [{"title": "Driver", "value": "Large loss"}, {"title": "7-day LR", "value": "209% (target 66%, +143 pts)"}, {"title": "30-day LR", "value": "94%"}, {"title": "Alert", "value": "LR-20261116-LIA-SOUT"}]}, {"type": ...

[slack dry-run] LR-20261116-MOT-UK
{"text": "Loss ratio RED: Motor / UK & Ireland", "blocks": [{"type": "header", "text": {"type": "plain_text", "text": "Loss ratio alert: Motor, UK & Ireland"}}, {"type": "section", "fields": [{"type": "mrkdwn", "text": "*Status*\n:red_circle: RED"}, {"type": "mrkdwn", "text": "*Driver*\nFrequency"}, {"type": "mrkdwn", "text": "*7-day LR*\n104% vs target 70% (+34 pts)"}, {"type": "mrkdwn", "text": "*30-day LR*\n84%"}]}, {"type": "section", "text": {"type": "mrkdwn", "text": "*Why (Genie)*\nYou want to understand why the Motor line of business loss ratio in the UK & Ireland region increased over...

[teams dry-run] LR-20261116-MOT-UK
{"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.4", "body": [{"type": "TextBlock", "size": "Large", "weight": "Bolder", "text": "Loss ratio RED: Motor, UK & Ireland", "color": "Attention"}, {"type": "FactSet", "facts": [{"title": "Driver", "value": "Frequency"}, {"title": "7-day LR", "value": "104% (target 70%, +34 pts)"}, {"title": "30-day LR", "value": "84%"}, {"title": "Alert", "value": "LR-20261116-MOT-UK"}]}, {"type": "TextBlock"...

[slack dry-run] LR-20261116-LIA-UK
{"text": "Loss ratio AMBER: Liability / UK & Ireland", "blocks": [{"type": "header", "text": {"type": "plain_text", "
```

## Task `lakebase_publish_and_transact` · `src/lakebase/02_publish_and_transact`


**Cell** `inst = ensure_instance(INSTANCE)`

```text
400 actions for 6 alerts; 20 watchlist segments
```

**Cell** `import time`

```text
published 0 new actions · proposed 0 rate actions
ops.lr_actions 16
pricing.quotes 24300
pricing.rate_actions 2
```

**Cell** `from databricks.sdk.service.database import SyncedDatabaseTable, SyncedTableSpec, SyncedTableSchedulingPolicy`

```text
refreshing synced table <catalog>.loss_ratio_coworker.lr_watchlist_serving (pipeline <service-principal>)
```

**Cell** `# The synced table is created asynchronously: wait (up to ~10 min) until it is online, then grant`

```text
synced table state: SyncedTableState.SYNCED_TABLE_ONLINE_UPDATING_PIPELINE_RESOURCES
granted app lrc-action-desk (<service-principal>) access to ops, pricing and synced schema loss_ratio_coworker
```

## Task `lakebase_snapshot_to_delta` · `src/lakebase/03_snapshot_to_delta`


**Cell** `import pandas as pd`

```text
lr_action_status: 16 rows
bronze_pricing_quotes: 24,300 rows
bronze_rate_actions: 2 rows
```
| team | status | actions |
|---|---|---|
| Claims | ACKNOWLEDGED | 1 |
| Claims | IN_PROGRESS | 1 |
| Claims | OPEN | 2 |
| Finance | OPEN | 1 |
| Pricing | OPEN | 2 |
| Reinsurance | OPEN | 2 |
| Reserving | OPEN | 1 |
| Underwriting | OPEN | 6 |

**Cell** `# Re-apply the app grants (covers the synced table if it came online after Lakebase 02)`

```text
granted app lrc-action-desk (<service-principal>) access to ops, pricing and synced schema loss_ratio_coworker
```

## Task `train_frequency_forecast` · `src/ml/06_train_frequency_forecast`


**Cell** `import numpy as np`

```text
1,700 weekly rows · 20 segments · 20 features
```

**Cell** `import mlflow`

```text
If you are using MLflow Tracing, you can migrate your traces to Unity Catalog for unlimited storage, fine-grained access controls, and queryability from notebooks, SQL, and dashboards. Learn more: https://docs.databricks.com/aws/en/mlflow3/genai/tracing/migrate-traces-to-uc
2026/11/16 05:15:10 WARNING mlflow.models.model: `artifact_path` is deprecated. Please use `name` instead.
🔗 View Logged Model at: <workspace-url>
Registered model '<catalog>.loss_ratio_coworker.lrc_frequency_forecast' already exists. Creating a new version of this model...
```
```text
🔗 Created version '2' of model '<catalog>.loss_ratio_coworker.lrc_frequency_forecast': <workspace-url>
```
```text
hold-out MAE: model 5.44 vs naive 6.84 claims/week → +20.4% better than naive
```

**Cell** `from mlflow import MlflowClient`

```text
<catalog>.loss_ratio_coworker.lrc_frequency_forecast v2 → alias champion
```

**Cell** `champion = mlflow.sklearn.load_model(f"models:/{MODEL}@champion")`

| as_of_date | line_of_business | region | claims_last7 | forecast_next7_claims | weekly_avg_last4 | forecast_vs_4wk_avg_pct | frequency_outlook | model_version |
|---|---|---|---|---|---|---|---|---|
| 2026-11-11T00:00:00.000Z | Marine | Benelux | 8.0 | 10.8 | 8.25 | 30.9 | RISING | 2 |
| 2026-11-11T00:00:00.000Z | Liability | UK & Ireland | 26.0 | 29.7 | 24.25 | 22.5 | RISING | 2 |
| 2026-11-11T00:00:00.000Z | Property | Southern Europe | 24.0 | 37.1 | 32.0 | 15.9 | RISING | 2 |
| 2026-11-11T00:00:00.000Z | Marine | France | 16.0 | 18.6 | 16.25 | 14.5 | STABLE | 2 |
| 2026-11-11T00:00:00.000Z | Marine | Southern Europe | 12.0 | 15.6 | 14.0 | 11.4 | STABLE | 2 |
| 2026-11-11T00:00:00.000Z | Marine | DACH | 23.0 | 22.3 | 21.0 | 6.2 | STABLE | 2 |
| 2026-11-11T00:00:00.000Z | Property | UK & Ireland | 46.0 | 48.4 | 46.75 | 3.5 | STABLE | 2 |
| 2026-11-11T00:00:00.000Z | Liability | Benelux | 20.0 | 13.9 | 13.5 | 3.0 | STABLE | 2 |
| 2026-11-11T00:00:00.000Z | Motor | France | 85.0 | 85.1 | 83.0 | 2.5 | STABLE | 2 |
| 2026-11-11T00:00:00.000Z | Motor | Benelux | 56.0 | 53.3 | 52.25 | 2.0 | STABLE | 2 |
| 2026-11-11T00:00:00.000Z | Property | France | 39.0 | 38.2 | 38.25 | -0.1 | STABLE | 2 |
| 2026-11-11T00:00:00.000Z | Property | Benelux | 22.0 | 23.1 | 23.5 | -1.7 | STABLE | 2 |
| 2026-11-11T00:00:00.000Z | Motor | Southern Europe | 87.0 | 75.8 | 78.75 | -3.7 | STABLE | 2 |
| 2026-11-11T00:00:00.000Z | Motor | DACH | 98.0 | 92.1 | 96.0 | -4.1 | STABLE | 2 |
| 2026-11-11T00:00:00.000Z | Liability | Southern Europe | 17.0 | 20.1 | 21.0 | -4.3 | STABLE | 2 |
| 2026-11-11T00:00:00.000Z | Property | DACH | 81.0 | 47.9 | 50.25 | -4.7 | STABLE | 2 |
| 2026-11-11T00:00:00.000Z | Liability | DACH | 27.0 | 24.9 | 26.75 | -6.9 | STABLE | 2 |
| 2026-11-11T00:00:00.000Z | Liability | France | 19.0 | 21.6 | 23.75 | -9.1 | STABLE | 2 |
| 2026-11-11T00:00:00.000Z | Marine | UK & Ireland | 21.0 | 21.5 | 25.0 | -14.0 | STABLE | 2 |
| 2026-11-11T00:00:00.000Z | Motor | UK & Ireland | 149.0 | 109.1 | 127.25 | -14.3 | STABLE | 2 |

**Cell** `esc = spark.sql(f"""`

| line_of_business | region | claims_last7 | forecast_next7_claims | forecast_vs_4wk_avg_pct | team | priority | lakebase_status | action |
|---|---|---|---|---|---|---|---|---|
| Liability | UK & Ireland | 26.0 | 29.7 | 22.5 | Underwriting | P2 | OPEN | Monitor. No action unless the 30-day loss ratio also breaches. |

## Task `evaluate_genai_dq` · `src/genai/04_evaluate_genai_dq`


**Cell** `spark.sql(f"""`

| claim_id | report_date | coded_cause | source_cause | ai_peril | loss_description_masked | truth_peril_mismatch | flag_peril_mismatch | truth_pii | flag_pii |
|---|---|---|---|---|---|---|---|---|---|
| CLM-3075616 | 2026-11-02 | Third-Party PD | Third-Party PD | third-party property damage | Our vehicle damaged a third-party bus shelter in Dublin. Contact [MASKED] on [MASKED] or [MASKED] | False | False | True | True |
| CLM-3075712 | 2026-11-03 | Third-Party BI | Third-Party BI | bodily injury | Pedestrian injured when our delivery vehicle mounted the kerb in Leeds. Contact [MASKED] on [MASKED] or [MASKED] | False | False | True | True |
| CLM-3075742 | 2026-11-03 | Heavy Weather | Heavy Weather | heavy weather at sea | Heavy seas caused containers to shift and fall overboard en route to Munich. Contact [MASKED] on [MASKED] or [MASKED] | False | False | True | True |
| CLM-3075745 | 2026-11-03 | Third-Party PD | Third-Party PD | third-party property damage | Our vehicle damaged a third-party bus shelter in Utrecht. Contact [MASKED] on [MASKED] or [MASKED] | False | False | True | True |
| CLM-3075748 | 2026-11-03 | Third-Party BI | Third-Party BI | bodily injury | Pedestrian injured when our delivery vehicle mounted the kerb in Rotterdam. Contact [MASKED] on [MASKED] or [MASKED] | False | False | True | True |
| CLM-3075754 | 2026-11-03 | Theft | Collision | vehicle collision | Delivery van rear-ended at traffic lights in Nantes, bumper and tailgate damaged | True | True | False | False |
| CLM-3075755 | 2026-11-03 | Third-Party BI | Third-Party BI | bodily injury | [MASKED] injured when our delivery vehicle mounted the kerb in Lille | False | False | False | True |
| CLM-3075838 | 2026-11-04 | Collision | Collision | vehicle collision | Company car collided with a parked vehicle while reversing in Munich. Contact [MASKED] on [MASKED] or [MASKED] | False | False | True | True |
| CLM-3075865 | 2026-11-04 | Collision | Collision | vehicle collision | Company car collided with a parked vehicle while reversing in Zurich. Contact [MASKED] on [MASKED] or [MASKED] | False | False | True | True |
| CLM-3075874 | 2026-11-04 | Storm/Wind | Storm/Wind | storm or wind | Fallen tree after windstorm damaged the office facade in Munich. Contact [MASKED] on [MASKED] or [MASKED] | False | False | True | True |
| CLM-3075880 | 2026-11-04 | Third-Party BI | Third-Party BI | bodily injury | Cyclist reports neck injury after collision with fleet car in Porto. Contact [MASKED] on [MASKED] or [MASKED] | False | False | True | True |
| CLM-3075899 | 2026-11-05 | Cargo Damage | Cargo Damage | water damage | Container of electronics arrived water-damaged at the port near Bristol. Contact [MASKED] on [MASKED] or [MASKED] | False | False | True | True |
| CLM-3075901 | 2026-11-05 | Collision | Collision | vehicle collision | Company car collided with a parked vehicle while reversing in Stuttgart. Contact [MASKED] on [MASKED] or [MASKED] | False | False | True | True |
| CLM-3075927 | 2026-11-05 | Third-Party BI | Third-Party BI | bodily injury | Pedestrian injured when our delivery vehicle mounted the kerb in Lyon. Contact [MASKED] on [MASKED] or [MASKED] | False | False | True | True |
| CLM-3075958 | 2026-11-05 | Theft | Collision | vehicle collision | Delivery van rear-ended at traffic lights in Liège, bumper and tailgate damaged | True | True | False | False |
| CLM-3075977 | 2026-11-05 | Collision | Collision | vehicle collision | Delivery van rear-ended at traffic lights in Lyon, bumper and tailgate damaged. Contact [MASKED] on [MASKED] or [MASKED] | False | False | True | True |
| CLM-3075980 | 2026-11-05 | Hail | Hail | hail | Hailstones damaged roof tiles and skylights at the insured warehouse in Manchester. Contact [MASKED] on [MASKED] or [MASKED] | False | False | True | True |
| CLM-3075981 | 2026-11-05 | Vessel Collision | Vessel Collision | vessel collision | Feeder vessel struck the quay while berthing near [MASKED] | False | False | False | True |
| CLM-3075982 | 2026-11-05 | Third-Party PD | Third-Party PD | third-party property damage | Insured truck scraped a third party's gate while turning in Lyon. Contact [MASKED] on [MASKED] or [MASKED] | False | False | True | True |
| CLM-3076011 | 2026-11-05 | Third-Party PD | Third-Party PD | third-party property damage | Insured truck scraped a third party's gate while turning in [MASKED] | False | False | False | True |

_30 more rows in the CSV._

**Cell** `ev = spark.sql(f"""`

| evaluated_at | check_name | genai_function | claims_checked | seeded_defects | flagged | true_positives | false_positives | false_negatives | precision | recall | f1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-11-16T05:20:36.222Z | peril_mismatch | ai_classify | 1981 | 21 | 23 | 21 | 2 | 0 | 0.913 | 1.0 | 0.955 |
| 2026-11-16T05:20:36.222Z | pii_in_free_text | ai_mask | 1981 | 70 | 86 | 70 | 16 | 0 | 0.814 | 1.0 | 0.897 |

**Cell** `display(spark.sql("""`

| kind | claim_id | coded_cause | ai_peril | loss_description_masked |
|---|---|---|---|---|
| peril false alarm | CLM-3076076 | Theft | cargo theft | Thieves cut the fence at the Antwerp yard and removed copper cable |
| peril false alarm | CLM-3076151 | Theft | cargo theft | Thieves cut the fence at the Rotterdam yard and removed copper cable |

**Cell** `judged = spark.sql(f"""`

| check_name | judged | correct_check | actionable | no_personal_data | faithful | avg_score |
|---|---|---|---|---|---|---|
| negative_amount | 2 | 1.0 | 1.0 | 1.0 | 0.5 | 3.0 |
| non_eur_currency | 4 | 1.0 | 1.0 | 1.0 | 0.25 | 2.5 |
| peril_mismatch | 6 | 1.0 | 1.0 | 1.0 | 1.0 | 4.8 |
| pii_in_free_text | 28 | 0.857 | 1.0 | 1.0 | 0.893 | 3.46 |
|  | 40 | 0.897 | 1.0 | 1.0 | 0.821 | 3.51 |
| check_name | score | reason | ai_explanation |
|---|---|---|---|
| negative_amount | 3 | Correctly flags the negative incurred amount and says to make it positive, but ignores that negatives can be legitimate reserve reductions or recoveries. | The issue is that the incurred amount is negative (-23704.0), which is inconsistent with a legitimate claim. The claims handler should update the incurred amount to a positive value, as claims amounts cannot be negative. |
| pii_in_free_text | 2 | Explains a cause-code mismatch rather than the failed pii_in_free_text check; ignores masked contact details in the description. | The issue is that the coded cause of loss is "Cargo Damage" but the description suggests "water damage", indicating a potential inconsistency. The claims handler should update the coded cause of loss to "Water Damage" to |
| pii_in_free_text | 3 | Names the PII check and says to mask or remove it, but is generic. It ignores that the text is already masked and doesn't say what to change. | The issue is that the description field contains free text that may potentially include personally identifiable information (PII), which is not allowed. The claims handler should mask or remove any sensitive information  |
| pii_in_free_text | 3 | Addresses PII in free text and says to re-mask or remove it, but it is generic and ignores that the description is already masked. | The issue is that the description field contains free text that may potentially include personally identifiable information (PII), which is not allowed. The claims handler should re-mask or remove any sensitive informati |
| non_eur_currency | 2 | Names the non-EUR check, but Zurich is in Switzerland (CHF), so 'match location' is wrong; the amount and currency are not in the inputs. | The issue is that the incurred amount (41,225.0) is not in Euros, despite the location being Zurich, which suggests a European currency. The claims handler should update the currency of the incurred amount to Euros (EUR) |
| pii_in_free_text | 2 | Blames the city Stuttgart as PII, ignoring the masked personal identifier; advice is misdirected and the claim is speculative. | The issue is that the description field contains location-specific information (Stuttgart) which may be considered personal or sensitive data. The claims handler should remove or mask the location (Stuttgart) from the de |
| pii_in_free_text | 3 | Names the PII check and says to mask or remove it, but is generic and does not say what was flagged. | The issue is that the description field contains free text that may potentially include personally identifiable information (PII), which is not allowed. The claims handler should mask or remove any sensitive information  |
| negative_amount | 3 | Explains negative_amount and gives a fix, but the -23951.0 value and 'incurred' field are not in the inputs, and it overlooks legitimate negatives such as recoveries. | The issue is that the incurred amount is negative (-23951.0), which is inconsistent with a valid claim. The claims handler should update the incurred amount to a positive value, as claims amounts cannot be negative. |
| pii_in_free_text | 2 | Flags 'Vienna' as PII and ignores the masked contact details, which are the real PII; the fix is misdirected. | The issue is that the description contains location information ("Vienna") which may be considered personal identifiable information (PII). The claims handler should remove or mask the location to fix the issue and ensur |
| non_eur_currency | 2 | Addresses the currency check, but the amount 7450.0 is not in the inputs, and the fix is vague (convert or relabel?). | The issue is that the incurred amount of 7450.0 is not in Euros, as required. The claims handler should update the incurred amount to the correct currency, presumably Euros, to resolve the non_eur_currency check failure. |
