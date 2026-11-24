-- Lakeflow Spark Declarative Pipeline · SILVER + DATA QUALITY (added by notebooks/03_silver_data_quality)
--
-- Types, de-duplicates and checks the bronze records with expectations, attaches the Unity Catalog row filter and
-- column mask, then runs Gen AI checks on the free text of the most recent claims: ai_classify (peril vs coded cause),
-- ai_mask (personal data) and ai_query (a plain-English explanation and fix per issue).
-- Configuration: policy_schema, llm_endpoint, ai_lookback_days, max_ai_claims

-- ═══ SILVER: typed, de-duplicated, rule-based expectations ═══════════════════════════════════════════════════════

-- Unity Catalog policies (functions created at the start of notebooks/03_silver_data_quality):
--   row filter   ${policy_schema}.lrc_region_filter(region)        a claims team sees only its own region's book
--   column mask  ${policy_schema}.lrc_mask_free_text(description)  raw free text only for lrc_pii_readers (GDPR)
CREATE OR REFRESH MATERIALIZED VIEW silver_claims (
  claim_id STRING, policy_id STRING, line_of_business STRING, region STRING,
  loss_date DATE COMMENT 'Date the loss event happened.',
  report_date DATE COMMENT 'Date the claim was reported to the insurer. The daily loss ratio uses this date.',
  cause_of_loss STRING COMMENT 'Peril that caused the loss (e.g. Hail, Collision, Bodily Injury).',
  incurred_loss DOUBLE COMMENT 'Paid loss plus case reserve for the claim (EUR), before recoveries.',
  paid_loss DOUBLE, case_reserve DOUBLE, claim_status STRING, currency STRING,
  event_tag STRING COMMENT 'Named event the claim belongs to, null for attritional claims.',
  large_loss_flag BOOLEAN COMMENT 'True when incurred loss is EUR 250k or more.',
  cat_event_flag BOOLEAN COMMENT 'True when the claim belongs to a catastrophe event.',
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
          cause_of_loss, incurred_loss, paid_loss, case_reserve, claim_status, currency, event_tag,
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
COMMENT 'Gen AI data quality on the most recent claims (at most max_ai_claims): ai_classify infers the peril from the free-text description and compares it with the coded cause of loss; ai_mask redacts personal data. Only the masked text is kept.'
AS
WITH recent AS (
  SELECT * FROM silver_claims
  WHERE report_date >= date_sub(current_date(), CAST('${ai_lookback_days}' AS INT))
  QUALIFY ROW_NUMBER() OVER (ORDER BY report_date DESC, claim_id) <= CAST('${max_ai_claims}' AS INT)   -- bounds token cost
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
