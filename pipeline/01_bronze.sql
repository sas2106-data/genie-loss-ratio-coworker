-- Lakeflow Spark Declarative Pipeline · BRONZE (added by notebooks/02_bronze)
--
-- Auto Loader (read_files as a stream) picks up every new file in the raw volume exactly once and keeps it as it
-- landed, plus the source file and ingestion time. Configuration: raw_path = /Volumes/<catalog>/<schema>/raw

CREATE OR REFRESH STREAMING TABLE bronze_fnol
COMMENT 'Bronze: first-notice-of-loss claim records exactly as landed in the raw volume (JSON), with source file and ingestion time.'
AS SELECT *, _metadata.file_path AS source_file, current_timestamp() AS ingested_at
FROM STREAM read_files('${raw_path}/claims_fnol/', format => 'json',
                       schemaHints => 'claim_id STRING, policy_id STRING, loss_date STRING, report_date STRING, incurred_loss DOUBLE, paid_loss DOUBLE, case_reserve DOUBLE, currency STRING');

CREATE OR REFRESH STREAMING TABLE bronze_premium
COMMENT 'Bronze: premium bordereaux exactly as landed in the raw volume (CSV), with source file and ingestion time.'
AS SELECT *, _metadata.file_path AS source_file, current_timestamp() AS ingested_at
FROM STREAM read_files('${raw_path}/premium_bordereaux/', format => 'csv', header => true,
                       schemaHints => 'as_of_date STRING, earned_premium DOUBLE');
