# 08 · Unity Catalog governance: row filter and column mask on claims

Functions from [`src/governance/05_row_filter_column_mask.py`](../../src/governance/05_row_filter_column_mask.py), attached by the pipeline (`MASK` and `WITH ROW FILTER` in [`src/pipeline/lrc_ingest_pipeline.sql`](../../src/pipeline/lrc_ingest_pipeline.sql)).


## Row filters attached (information_schema)

| table_name | filter_name | target_columns |
|---|---|---|
| silver_claims | <catalog>.loss_ratio_coworker.lrc_region_filter | region |
| gold_daily_loss_run | <catalog>.loss_ratio_coworker.lrc_region_filter | region |


## Column masks attached (information_schema)

| table_name | column_name | mask_name |
|---|---|---|
| silver_claims | loss_description | <catalog>.loss_ratio_coworker.lrc_mask_free_text |


## Which group sees which book (row filter mapping)

| group_name | claims_visible |
|---|---|
| lrc_claims_all | 3716 |
| lrc_claims_benelux | 400 |
| lrc_claims_dach | 1020 |
| lrc_claims_france | 679 |
| lrc_claims_southern_europe | 617 |
| lrc_claims_uk | 1000 |


## What a non-PII reader sees (column mask redaction)

| claim_id | region | seen_by_everyone_else |
|---|---|---|
| CLM-3073814 | UK & Ireland | Burst pipe on the third floor caused water damage to offices below in Dublin. Contact [name] on [phone] or [email] |
| CLM-3073822 | Benelux | Heavy seas caused containers to shift and fall overboard en route to Antwerp. Contact [name] on [phone] or [email] |
| CLM-3073903 | Benelux | Delivery van rear-ended at traffic lights in Rotterdam, bumper and tailgate damaged. Contact [name] on [phone] or [email] |
| CLM-3073906 | UK & Ireland | Company car collided with a parked vehicle while reversing in Dublin. Contact [name] on [phone] or [email] |
| CLM-3073908 | UK & Ireland | Container seal broken, part of the cargo missing on arrival in Dublin. Contact [name] on [phone] or [email] |
| CLM-3073912 | Southern Europe | River flooding entered the ground floor of the Milan depot, water 40cm deep. Contact [name] on [phone] or [email] |
