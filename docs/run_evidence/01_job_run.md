# 01 · Job run: `[LRC] 0 · End-to-end daily run: sources → Lakeflow → Gen AI DQ → Lakebase → Genie`

| | |
|---|---|
| Job id | `787860233236136` |
| Run id | `945039689803583` |
| Result | **SUCCESS** |
| Started | 2026-11-16 05:50:41 UTC |
| Wall-clock | 17.9 min |
| Run URL | <workspace-url> |

Defined in [`databricks.yml`](../../databricks.yml) (job `lrc_end_to_end`).

| Task | Type | Depends on | Result | Started | Duration |
|---|---|---|---|---|---|
| governance_policies | notebook |  | SUCCESS | 2026-11-16 05:50:41 UTC | 0.7 min |
| generate_loss_run | notebook |  | SUCCESS | 2026-11-16 05:50:41 UTC | 0.8 min |
| lakebase_setup | notebook |  | SUCCESS | 2026-11-16 05:50:41 UTC | 0.6 min |
| land_raw_files | notebook | generate_loss_run | SUCCESS | 2026-11-16 05:51:26 UTC | 1.2 min |
| semantic_layer | notebook | generate_loss_run, governance_policies | SUCCESS | 2026-11-16 05:51:26 UTC | 0.7 min |
| watch_and_explain | notebook | semantic_layer, lakebase_setup | SUCCESS | 2026-11-16 05:52:06 UTC | 9.2 min |
| lakebase_publish_and_transact | notebook | watch_and_explain | SUCCESS | 2026-11-16 06:01:21 UTC | 0.5 min |
| lakebase_snapshot_to_delta | notebook | lakebase_publish_and_transact | SUCCESS | 2026-11-16 06:01:48 UTC | 0.5 min |
| lakeflow_ingest_and_ai_dq | Lakeflow pipeline | land_raw_files, lakebase_snapshot_to_delta, governance_policies | SUCCESS | 2026-11-16 06:02:17 UTC | 5.2 min |
| train_frequency_forecast | notebook | semantic_layer, lakebase_snapshot_to_delta | SUCCESS | 2026-11-16 06:02:17 UTC | 1.5 min |
| evaluate_genai_dq | notebook | lakeflow_ingest_and_ai_dq | SUCCESS | 2026-11-16 06:07:32 UTC | 1.0 min |
