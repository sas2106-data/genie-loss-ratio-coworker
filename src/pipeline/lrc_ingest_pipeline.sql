-- Lakeflow Spark Declarative Pipeline: raw volume → bronze → silver → Gen AI data quality → gold
--
-- Ingests the synthetic source files landed by src/raw/03_land_raw_files.py with Auto Loader, cleans and
-- de-duplicates them with expectations, runs Gen AI data-quality checks on the free-text loss descriptions, and
-- publishes a gold daily loss run with the same shape as gold_daily_loss_run. It also builds gold_rate_adequacy from
-- the Lakebase pricing snapshot (src/lakebase/03_snapshot_to_delta.py).
--
-- Pipeline configuration (set by databricks.yml):
--   raw_path          /Volumes/<catalog>/<schema>/raw
--   llm_endpoint      a Foundation Model API chat endpoint, e.g. databricks-meta-llama-3-3-70b-instruct
--   ai_lookback_days  how many report days the AI checks cover (bounds token cost), e.g. 14

-- ═══ BRONZE: files as they landed, plus ingestion metadata ═══════════════════════════════════════════════════════

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

-- ═══ SILVER: typed, de-duplicated, rule-based expectations ═══════════════════════════════════════════════════════

-- Unity Catalog policies (functions created by src/governance/05_row_filter_column_mask.py):
--   row filter   ${policy_schema}.lrc_region_filter(region)        a claims team sees only its own region's book
--   column mask  ${policy_schema}.lrc_mask_free_text(description)  raw free text only for lrc_pii_readers (GDPR)
CREATE OR REFRESH MATERIALIZED VIEW silver_claims (
  claim_id STRING, policy_id STRING, line_of_business STRING, region STRING, loss_date DATE, report_date DATE,
  cause_of_loss STRING, incurred_loss DOUBLE, paid_loss DOUBLE, case_reserve DOUBLE, currency STRING, event_tag STRING,
  large_loss_flag BOOLEAN, cat_event_flag BOOLEAN,
  loss_description STRING MASK ${policy_schema}.lrc_mask_free_text,
  source_system STRING, source_file STRING, ingested_at TIMESTAMP,
  CONSTRAINT has_claim_id        EXPECT (claim_id IS NOT NULL)            ON VIOLATION DROP ROW,
  CONSTRAINT report_not_future   EXPECT (report_date <= current_date())   ON VIOLATION DROP ROW,
  CONSTRAINT loss_before_report  EXPECT (loss_date <= report_date),
  CONSTRAINT non_negative_amount EXPECT (incurred_loss >= 0),
  CONSTRAINT currency_is_eur     EXPECT (currency = 'EUR')
)
WITH ROW FILTER ${policy_schema}.lrc_region_filter ON (region)
COMMENT 'Silver: one row per claim (latest version), typed dates and amounts, rule-based expectations recorded in the pipeline event log. Row filter by region; free text masked for non-PII readers.'
AS SELECT claim_id, policy_id, line_of_business, region,
          CAST(loss_date AS DATE) AS loss_date, CAST(report_date AS DATE) AS report_date,
          cause_of_loss, incurred_loss, paid_loss, case_reserve, currency, event_tag,
          incurred_loss >= 250000 AS large_loss_flag, event_tag = 'Hailstorm DACH' AS cat_event_flag,
          loss_description, source_system, source_file, ingested_at
FROM bronze_fnol
QUALIFY ROW_NUMBER() OVER (PARTITION BY claim_id ORDER BY ingested_at DESC, source_file DESC) = 1;

CREATE OR REFRESH MATERIALIZED VIEW silver_premium (
  CONSTRAINT positive_premium EXPECT (earned_premium > 0) ON VIOLATION DROP ROW,
  CONSTRAINT currency_is_eur  EXPECT (currency = 'EUR')
)
COMMENT 'Silver: earned premium per day, line of business and region from the bordereaux (latest file wins).'
AS SELECT CAST(as_of_date AS DATE) AS as_of_date, line_of_business, region, earned_premium, currency, bordereau_id, source_file
FROM bronze_premium
QUALIFY ROW_NUMBER() OVER (PARTITION BY as_of_date, line_of_business, region ORDER BY ingested_at DESC) = 1;

-- ═══ GEN AI DATA QUALITY: read the free text, not just the codes ═════════════════════════════════════════════════

CREATE OR REFRESH MATERIALIZED VIEW silver_claims_ai_checked
COMMENT 'Gen AI data quality on recent claims: ai_classify infers the peril from the free-text description and compares it with the coded cause of loss; ai_mask redacts personal data. Only the masked text is kept.'
AS
WITH recent AS (
  SELECT * FROM silver_claims
  WHERE report_date >= date_sub(current_date(), CAST('${ai_lookback_days}' AS INT))
),
ai AS (
  SELECT *,
         ai_classify(loss_description, ARRAY('hail', 'fire', 'flood', 'storm or wind', 'water damage', 'theft',
                                             'vehicle collision', 'bodily injury', 'third-party property damage',
                                             'professional error', 'product defect', 'cargo damage', 'cargo theft',
                                             'vessel collision', 'heavy weather at sea')) AS ai_peril,
         -- labels exclude 'address': city names in a loss description are not personal data
         ai_mask(loss_description, ARRAY('person', 'phone number', 'email')) AS loss_description_masked
  FROM recent
)
SELECT * EXCEPT (loss_description),   -- raw text stays only in policy-protected silver_claims
       CASE ai_peril
         WHEN 'hail' THEN cause_of_loss IN ('Hail', 'Weather')
         WHEN 'fire' THEN cause_of_loss IN ('Fire', 'Product Liability')            -- a product that overheats and burns
         WHEN 'flood' THEN cause_of_loss = 'Flood'
         WHEN 'storm or wind' THEN cause_of_loss IN ('Storm/Wind', 'Weather', 'Heavy Weather')
         WHEN 'water damage' THEN cause_of_loss IN ('Water Damage', 'Cargo Damage')
         WHEN 'theft' THEN cause_of_loss IN ('Theft', 'Cargo Theft')
         WHEN 'vehicle collision' THEN cause_of_loss IN ('Collision', 'Third-Party PD', 'Third-Party BI')
         WHEN 'bodily injury' THEN cause_of_loss IN ('Bodily Injury', 'Third-Party BI')
         WHEN 'third-party property damage' THEN cause_of_loss IN ('Property Damage', 'Third-Party PD', 'Product Liability')
         WHEN 'professional error' THEN cause_of_loss IN ('Professional Error', 'Property Damage')  -- workmanship damage
         WHEN 'product defect' THEN cause_of_loss = 'Product Liability'
         WHEN 'cargo damage' THEN cause_of_loss IN ('Cargo Damage', 'Heavy Weather', 'Water Damage')  -- cargo damaged by weather or water
         WHEN 'cargo theft' THEN cause_of_loss = 'Cargo Theft'
         WHEN 'vessel collision' THEN cause_of_loss = 'Vessel Collision'
         WHEN 'heavy weather at sea' THEN cause_of_loss = 'Heavy Weather'
         ELSE TRUE END                                AS peril_consistent,
       loss_description_masked <> loss_description   AS pii_detected
FROM ai;

CREATE OR REFRESH MATERIALIZED VIEW dq_claims_issues
COMMENT 'One row per data-quality issue: rule-based checks and Gen AI checks, each with a plain-English explanation and suggested fix written by ai_query (personal data already masked).'
AS
WITH issues AS (
  SELECT claim_id, report_date, line_of_business, region, cause_of_loss, ai_peril, incurred_loss,
         loss_description_masked, 'peril_mismatch' AS check_name, 'Gen AI' AS check_type, 'High' AS severity
  FROM silver_claims_ai_checked WHERE NOT peril_consistent
  UNION ALL
  SELECT claim_id, report_date, line_of_business, region, cause_of_loss, ai_peril, incurred_loss,
         loss_description_masked, 'pii_in_free_text', 'Gen AI', 'High'
  FROM silver_claims_ai_checked WHERE pii_detected
  UNION ALL
  SELECT claim_id, report_date, line_of_business, region, cause_of_loss, ai_peril, incurred_loss,
         loss_description_masked, 'negative_amount', 'Rule', 'Medium'
  FROM silver_claims_ai_checked WHERE incurred_loss < 0
  UNION ALL
  SELECT claim_id, report_date, line_of_business, region, cause_of_loss, ai_peril, incurred_loss,
         loss_description_masked, 'loss_after_report', 'Rule', 'Medium'
  FROM silver_claims_ai_checked WHERE loss_date > report_date
  UNION ALL
  SELECT claim_id, report_date, line_of_business, region, cause_of_loss, ai_peril, incurred_loss,
         loss_description_masked, 'non_eur_currency', 'Rule', 'Medium'
  FROM silver_claims_ai_checked WHERE currency <> 'EUR'
)
SELECT *,
       ai_query('${llm_endpoint}',
         concat('You are a claims data-quality analyst at a P&C insurer. In at most two short sentences, explain the issue ',
                'and suggest the fix a claims handler should make. Do not invent facts. ',
                'Check failed: ', check_name, '. Coded cause of loss: ', cause_of_loss,
                '. Peril inferred from the description: ', coalesce(ai_peril, 'n/a'),
                '. Incurred amount: ', cast(round(incurred_loss, 0) AS STRING),
                '. Description (personal data masked): ', loss_description_masked)) AS ai_explanation
FROM issues;

CREATE OR REFRESH MATERIALIZED VIEW dq_daily_scorecard
COMMENT 'Daily data-quality scorecard: records checked, issues and pass rate per check. Read by the dashboard, the Genie Agent and the morning brief.'
AS
WITH checked AS (
  SELECT report_date, COUNT(*) AS records_checked FROM silver_claims_ai_checked GROUP BY report_date
),
issues AS (
  SELECT report_date, check_name, check_type, severity, COUNT(DISTINCT claim_id) AS issues
  FROM dq_claims_issues GROUP BY ALL
)
SELECT i.report_date, i.check_name, i.check_type, i.severity, i.issues, c.records_checked,
       ROUND(1 - i.issues / c.records_checked, 4) AS pass_rate
FROM issues i JOIN checked c USING (report_date);

-- ═══ GOLD: the daily loss run from the governed pipeline ═════════════════════════════════════════════════════════

CREATE OR REFRESH MATERIALIZED VIEW gold_daily_loss_run_lf
COMMENT 'Gold (Lakeflow): incurred loss on the date reported and earned premium per day × line of business × region, built from the raw files. Same shape as gold_daily_loss_run; claims with a negative amount or non-EUR currency are excluded until fixed.'
AS
WITH c AS (
  SELECT report_date AS as_of_date, line_of_business, region,
         SUM(incurred_loss) AS incurred_loss, SUM(paid_loss) AS paid_loss, SUM(case_reserve) AS case_reserve,
         COUNT(*) AS claim_count,
         SUM(CASE WHEN large_loss_flag THEN incurred_loss ELSE 0 END) AS large_loss_incurred,
         SUM(CASE WHEN large_loss_flag THEN 1 ELSE 0 END) AS large_loss_count,
         SUM(CASE WHEN cat_event_flag THEN incurred_loss ELSE 0 END) AS cat_incurred
  FROM silver_claims WHERE incurred_loss >= 0 AND currency = 'EUR' GROUP BY ALL
)
SELECT p.as_of_date, p.line_of_business, p.region, p.earned_premium,
       COALESCE(c.incurred_loss, 0) incurred_loss, COALESCE(c.paid_loss, 0) paid_loss, COALESCE(c.case_reserve, 0) case_reserve,
       COALESCE(c.claim_count, 0) claim_count, COALESCE(c.large_loss_incurred, 0) large_loss_incurred,
       COALESCE(c.large_loss_count, 0) large_loss_count, COALESCE(c.cat_incurred, 0) cat_incurred
FROM silver_premium p
LEFT JOIN c ON p.as_of_date = c.as_of_date AND p.line_of_business = c.line_of_business AND p.region = c.region;

-- ═══ GOLD: rate adequacy, joining Lakebase pricing transactions with the loss ratio ══════════════════════════════

CREATE OR REFRESH MATERIALIZED VIEW gold_rate_adequacy
COMMENT 'Rate adequacy per line of business × region over the last 30 days. Indicated rate change = 30-day loss ratio ÷ target − 1 (loss-ratio method); compared with the rate change actually achieved on quotes in the Lakebase pricing system and with rate actions the coworker proposed.'
AS
WITH q AS (
  SELECT line_of_business, region, COUNT(*) AS quotes,
         AVG(CASE WHEN status = 'BOUND' THEN 1.0 ELSE 0.0 END) AS bind_ratio,
         AVG(CASE WHEN status = 'REFERRED' THEN 1.0 ELSE 0.0 END) AS referral_ratio,
         AVG(rate_change_pct) AS avg_rate_change_pct,
         AVG(quoted_premium / NULLIF(technical_premium, 0)) AS price_to_technical
  FROM bronze_pricing_quotes
  WHERE CAST(created_at AS DATE) > date_sub(current_date(), 30) GROUP BY ALL
),
ra AS (
  SELECT line_of_business, region, COUNT(*) AS proposed_rate_actions, MAX(rate_change_pct) AS max_proposed_rate_change_pct
  FROM bronze_rate_actions WHERE status = 'PROPOSED' GROUP BY ALL
),
lr AS (
  SELECT line_of_business, region, SUM(incurred_loss) / NULLIF(SUM(earned_premium), 0) AS loss_ratio_30d
  FROM gold_daily_loss_run_lf WHERE as_of_date > date_sub(current_date(), 30) GROUP BY ALL
),
j AS (
  SELECT lr.line_of_business, lr.region,
         ROUND(lr.loss_ratio_30d, 4) AS loss_ratio_30d, t.target_loss_ratio,
         ROUND((lr.loss_ratio_30d - t.target_loss_ratio) * 100, 1) AS lr_gap_pts,
         ROUND((lr.loss_ratio_30d / t.target_loss_ratio - 1) * 100, 1) AS indicated_rate_change_pct,
         q.quotes, ROUND(q.bind_ratio, 3) AS bind_ratio, ROUND(q.referral_ratio, 3) AS referral_ratio,
         ROUND(q.avg_rate_change_pct, 1) AS achieved_rate_change_pct, ROUND(q.price_to_technical, 3) AS price_to_technical,
         COALESCE(ra.proposed_rate_actions, 0) AS proposed_rate_actions, ra.max_proposed_rate_change_pct
  FROM lr
  JOIN lr_targets t USING (line_of_business)
  LEFT JOIN q USING (line_of_business, region)
  LEFT JOIN ra USING (line_of_business, region)
)
SELECT *,
       ROUND(indicated_rate_change_pct - COALESCE(achieved_rate_change_pct, 0), 1) AS rate_shortfall_pts,
       CASE WHEN indicated_rate_change_pct > COALESCE(achieved_rate_change_pct, 0) + 2 AND proposed_rate_actions > 0
              THEN 'Rate action proposed: awaiting pricing decision'
            WHEN indicated_rate_change_pct > COALESCE(achieved_rate_change_pct, 0) + 2
              THEN 'Rate inadequate: achieved rate change below indicated, no rate action'
            WHEN lr_gap_pts > 0 THEN 'Monitor: above target, achieved rate change covers the gap'
            ELSE 'Adequate' END AS adequacy_status
FROM j;
