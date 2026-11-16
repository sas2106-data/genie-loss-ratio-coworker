# 02 · Notebook outputs (captured from the job run)

Each section is one notebook task: the code that ran and the output it printed or displayed. Markdown cells and setup cells without output are omitted.


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


## Task `watch_and_explain` · `src/jobs/daily_loss_ratio_watch`


**Cell** `watch = spark.sql(f"""`

```text
6 segments need attention | book YTD LR 63.6%, COR 92.1% vs industry 92.9%
```

**Cell** `import pandas as pd`

```text
recorded 6 alerts and 16 actions
```

**Cell** `import json, requests`

```text
[slack dry-run] LR-20261116-PRO-DACH
{"text": "Loss ratio RED: Property / DACH", "blocks": [{"type": "header", "text": {"type": "plain_text", "text": "Loss ratio alert: Property, DACH"}}, {"type": "section", "fields": [{"type": "mrkdwn", "text": "*Status*\n:red_circle: RED"}, {"type": "mrkdwn", "text": "*Driver*\nCatastrophe event"}, {"type": "mrkdwn", "text": "*7-day LR*\n266% vs target 60% (+206 pts)"}, {"type": "mrkdwn", "text": "*30-day LR*\n98%"}]}, {"type": "section", "text": {"type": "mrkdwn", "text": "*Why (Genie)*\n- **265.9%** loss ratio over the last 7 days, **205.9 percentage points above** the **60.0%** target; the s...

[teams dry-run] LR-20261116-PRO-DACH
{"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.4", "body": [{"type": "TextBlock", "size": "Large", "weight": "Bolder", "text": "Loss ratio RED: Property, DACH", "color": "Attention"}, {"type": "FactSet", "facts": [{"title": "Driver", "value": "Catastrophe event"}, {"title": "7-day LR", "value": "266% (target 60%, +206 pts)"}, {"title": "30-day LR", "value": "98%"}, {"title": "Alert", "value": "LR-20261116-PRO-DACH"}]}, {"type": "Text...

[slack dry-run] LR-20261116-LIA-SOUT
{"text": "Loss ratio RED: Liability / Southern Europe", "blocks": [{"type": "header", "text": {"type": "plain_text", "text": "Loss ratio alert: Liability, Southern Europe"}}, {"type": "section", "fields": [{"type": "mrkdwn", "text": "*Status*\n:red_circle: RED"}, {"type": "mrkdwn", "text": "*Driver*\nLarge loss"}, {"type": "mrkdwn", "text": "*7-day LR*\n209% vs target 66% (+143 pts)"}, {"type": "mrkdwn", "text": "*30-day LR*\n94%"}]}, {"type": "section", "text": {"type": "mrkdwn", "text": "*Why (Genie)*\n- **209.0%** loss ratio over the last 7 days, which is **143.0 points above** the **66.0%*...

[teams dry-run] LR-20261116-LIA-SOUT
{"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.4", "body": [{"type": "TextBlock", "size": "Large", "weight": "Bolder", "text": "Loss ratio RED: Liability, Southern Europe", "color": "Attention"}, {"type": "FactSet", "facts": [{"title": "Driver", "value": "Large loss"}, {"title": "7-day LR", "value": "209% (target 66%, +143 pts)"}, {"title": "30-day LR", "value": "94%"}, {"title": "Alert", "value": "LR-20261116-LIA-SOUT"}]}, {"type": ...

[slack dry-run] LR-20261116-MOT-UK
{"text": "Loss ratio RED: Motor / UK & Ireland", "blocks": [{"type": "header", "text": {"type": "plain_text", "text": "Loss ratio alert: Motor, UK & Ireland"}}, {"type": "section", "fields": [{"type": "mrkdwn", "text": "*Status*\n:red_circle: RED"}, {"type": "mrkdwn", "text": "*Driver*\nFrequency"}, {"type": "mrkdwn", "text": "*7-day LR*\n104% vs target 70% (+34 pts)"}, {"type": "mrkdwn", "text": "*30-day LR*\n84%"}]}, {"type": "section", "text": {"type": "mrkdwn", "text": "*Why (Genie)*\n- **Motor UK & Ireland is at 103.5%**, which is **33.5 percentage points above** the **70.0% target**; the...

[teams dry-run] LR-20261116-MOT-UK
{"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.4", "body": [{"type": "TextBlock", "size": "Large", "weight": "Bolder", "text": "Loss ratio RED: Motor, UK & Ireland", "color": "Attention"}, {"type": "FactSet", "facts": [{"title": "Driver", "value": "Frequency"}, {"title": "7-day LR", "value": "104% (target 70%, +34 pts)"}, {"title": "30-day LR", "value": "84%"}, {"title": "Alert", "value": "LR-20261116-MOT-UK"}]}, {"type": "TextBlock"...

[slack dry-run] LR-20261116-LIA-UK
{"text": "Loss ratio AMBER: Liability / UK & Ireland", "blocks": [{"type": "header", "text": {"type": "plain_text", "
```

## Task `lakebase_publish_and_transact` · `src/lakebase/02_publish_and_transact`


**Cell** `inst = ensure_instance(INSTANCE)`

```text
144 actions for 6 alerts; 20 watchlist segments
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

**Cell** `# Re-apply the app grants (covers the synced table if it came online after Lakebase 02)`

```text
granted app lrc-action-desk (<service-principal>) access to ops, pricing and synced schema loss_ratio_coworker
```

## Task `evaluate_genai_dq` · `src/genai/04_evaluate_genai_dq`

