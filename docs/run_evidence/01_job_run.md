# 01 · Job run: `[LRC] 0 · End-to-end daily run: sources → Lakeflow → Gen AI DQ → Lakebase → Genie`

| | |
|---|---|
| Job id | `787860233236136` |
| Run id | `604951087142024` |
| Result | **SUCCESS** |
| Started | 2026-11-16 03:45:28 UTC |
| Wall-clock | 12.2 min |
| Run URL | <workspace-url> |

Defined in [`resources/lrc_jobs.yml`](../../resources/lrc_jobs.yml) (job `lrc_end_to_end`).

| Task | Type | Depends on | Result | Started | Duration |
|---|---|---|---|---|---|
| generate_loss_run | notebook |  | SUCCESS | 2026-11-16 03:45:28 UTC | 0.8 min |
| lakebase_setup | notebook |  | SUCCESS | 2026-11-16 03:45:28 UTC | 0.5 min |
| land_raw_files | notebook | generate_loss_run | SUCCESS | 2026-11-16 03:46:18 UTC | 1.4 min |
| semantic_layer | notebook | generate_loss_run | SUCCESS | 2026-11-16 03:46:18 UTC | 0.7 min |
| watch_and_explain | notebook | semantic_layer | SUCCESS | 2026-11-16 03:47:00 UTC | 4.3 min |
| lakebase_publish_and_transact | notebook | watch_and_explain, lakebase_setup | SUCCESS | 2026-11-16 03:51:18 UTC | 0.5 min |
| lakebase_snapshot_to_delta | notebook | lakebase_publish_and_transact | SUCCESS | 2026-11-16 03:51:47 UTC | 0.5 min |
| lakeflow_ingest_and_ai_dq | Lakeflow pipeline | land_raw_files, lakebase_snapshot_to_delta | SUCCESS | 2026-11-16 03:52:15 UTC | 4.7 min |
| evaluate_genai_dq | notebook | lakeflow_ingest_and_ai_dq | SUCCESS | 2026-11-16 03:57:00 UTC | 0.7 min |
