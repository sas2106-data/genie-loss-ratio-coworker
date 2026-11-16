# 05 · Lakebase operational store and the Action Desk app

## Instance

| Name | State | Capacity | Postgres | Read/write DNS |
|---|---|---|---|---|
| `lrc-lakebase` | AVAILABLE | CU_1 | PG_VERSION_16 | `ep-wispy-pine-d2mlyr2v.database.us-east-1.cloud.databricks.com` |

Defined in [`resources/lrc_lakebase.yml`](../../resources/lrc_lakebase.yml). Database `lrc_ops`, schemas `ops` and `pricing`
([`src/lakebase/01_setup_lakebase.py`](../../src/lakebase/01_setup_lakebase.py)).

## Synced table (Delta → Lakebase, for millisecond reads in the app)

| Synced table | Source Delta table | State | Message |
|---|---|---|---|
| <catalog>.loss_ratio_coworker.lr_watchlist_serving | <catalog>.loss_ratio_coworker.lr_watchlist_snapshot | SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE | Synced table creation succeeded using Delta Live Tables: <workspace-url> |

## Action Desk app (Databricks App with a Lakebase database resource)

| App | URL | App state | Compute |
|---|---|---|---|
| lrc-action-desk | <app-url> | RUNNING | ACTIVE |

Source: [`app/action_desk/app.py`](../../app/action_desk/app.py). Screenshot: [`action_desk.png`](action_desk.png) (if captured).

## Team status of actions (Lakebase `ops.lr_actions`, snapshotted to Delta `lr_action_status`)

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
