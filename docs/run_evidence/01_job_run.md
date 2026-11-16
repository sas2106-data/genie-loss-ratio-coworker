# 01 · Job run: `[LRC] 0 · End-to-end daily run: sources → Lakeflow → Gen AI DQ → Lakebase → Genie`

| | |
|---|---|
| Job id | `787860233236136` |
| Run id | `485868090598415` |
| Result | **SUCCESS** |
| Started | 2026-11-16 05:05:29 UTC |
| Wall-clock | 15.6 min |
| Run URL | <workspace-url> |

Defined in [`resources/lrc_jobs.yml`](../../resources/lrc_jobs.yml) (job `lrc_end_to_end`).

| Task | Type | Depends on | Result | Started | Duration |
|---|---|---|---|---|---|
| governance_policies | notebook |  | SUCCESS | 2026-11-16 05:05:29 UTC | 0.7 min |
| generate_loss_run | notebook |  | SUCCESS | 2026-11-16 05:05:29 UTC | 0.7 min |
| lakebase_setup | notebook |  | SUCCESS | 2026-11-16 05:05:29 UTC | 0.5 min |
| land_raw_files | notebook | generate_loss_run | SUCCESS | 2026-11-16 05:06:13 UTC | 1.2 min |
| semantic_layer | notebook | generate_loss_run | SUCCESS | 2026-11-16 05:06:13 UTC | 0.6 min |
| watch_and_explain | notebook | semantic_layer | SUCCESS | 2026-11-16 05:06:50 UTC | 6.7 min |
| lakebase_publish_and_transact | notebook | watch_and_explain, lakebase_setup | SUCCESS | 2026-11-16 05:13:30 UTC | 0.5 min |
| lakebase_snapshot_to_delta | notebook | lakebase_publish_and_transact | SUCCESS | 2026-11-16 05:13:59 UTC | 0.4 min |
| lakeflow_ingest_and_ai_dq | Lakeflow pipeline | land_raw_files, lakebase_snapshot_to_delta, governance_policies | SUCCESS | 2026-11-16 05:14:23 UTC | 5.7 min |
| train_frequency_forecast | notebook | semantic_layer, lakebase_snapshot_to_delta | SUCCESS | 2026-11-16 05:14:23 UTC | 1.3 min |
| evaluate_genai_dq | notebook | lakeflow_ingest_and_ai_dq | SUCCESS | 2026-11-16 05:20:07 UTC | 1.0 min |
