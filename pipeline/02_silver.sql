-- Lakeflow Spark Declarative Pipeline · SILVER with Gen AI data quality (added by notebooks/03_silver_data_quality)
--
-- Silver is where the data becomes trustworthy, and Gen AI is part of that quality gate, next to the rules:
--   1. claims_typed          (temporary view)  type the bronze records and keep the latest version of each claim
--   2. claims_genai_checks   (private, materialized: runs once per update, not published)
--                            ai_classify reads the free-text description and infers the peril; ai_mask finds personal
--                            data. Runs on the newest claims only (max_ai_claims within ai_lookback_days) to bound cost.
--   3. silver_claims         every claim with its Gen AI results, and BOTH kinds of expectations: rules (dates,
--                            amounts, currency) and Gen AI (peril matches the description, no personal data in free
--                            text). Violations are recorded in the pipeline's data-quality metrics; rows are kept so a
--                            handler can fix them. Unity Catalog row filter by region and column mask on the free text.
--   4. dq_claims_issues      one row per issue, with a plain-English explanation and fix written by ai_query
--   5. dq_daily_scorecard    pass rate per check and day
-- Configuration: policy_schema, llm_endpoint, ai_lookback_days, max_ai_claims

-- ═══ 1 · Typed, de-duplicated claims (pipeline-scoped) ══════════════════════════════════════════════════════════

CREATE TEMPORARY VIEW claims_typed
AS SELECT claim_id, policy_id, line_of_business, region,
          CAST(loss_date AS DATE) AS loss_date, CAST(report_date AS DATE) AS report_date,
          cause_of_loss, incurred_loss, paid_loss, case_reserve, claim_status, currency, event_tag,
          loss_description, source_system, source_file, ingested_at
FROM bronze_fnol
QUALIFY ROW_NUMBER() OVER (PARTITION BY claim_id ORDER BY ingested_at DESC, source_file DESC) = 1;

-- ═══ 2 · Gen AI checks on the free text (private: only the masked text and the verdicts leave this step) ════════

CREATE OR REFRESH PRIVATE MATERIALIZED VIEW claims_genai_checks
COMMENT 'Gen AI data-quality checks on the newest claims: peril inferred from the description (ai_classify) and personal data (ai_mask).'
AS
WITH recent AS (
  SELECT * FROM claims_typed
  WHERE claim_id IS NOT NULL AND report_date <= current_date()
    AND report_date >= date_sub(current_date(), CAST('${ai_lookback_days}' AS INT))
  QUALIFY ROW_NUMBER() OVER (ORDER BY report_date DESC, claim_id) <= CAST('${max_ai_claims}' AS INT)
),
ai AS (
  SELECT claim_id, cause_of_loss, loss_description,
         ai_classify(loss_description, ARRAY('hail', 'fire', 'flood', 'storm or wind', 'water damage', 'theft',
                                             'vehicle collision', 'bodily injury', 'third-party property damage',
                                             'professional error', 'product defect', 'cargo damage', 'cargo theft',
                                             'vessel collision', 'heavy weather at sea')) AS ai_peril,
         -- labels exclude 'address': city names in a loss description are not personal data
         ai_mask(loss_description, ARRAY('person', 'phone number', 'email')) AS loss_description_masked
  FROM recent
)
SELECT claim_id, ai_peril, loss_description_masked,
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

-- ═══ 3 · Silver claims: rules + Gen AI expectations, governed ═════════════════════════════════════════════════════

-- Unity Catalog policies (functions created at the start of notebooks/03_silver_data_quality):
--   row filter   ${policy_schema}.lrc_region_filter(region)        a claims team sees only its own region's book
--   column mask  ${policy_schema}.lrc_mask_free_text(description)  raw free text only for lrc_pii_readers (GDPR)
-- Expectations: the first five are rules, the last two are Gen AI checks. Both are recorded in the pipeline's
-- data-quality metrics, so the pipeline graph shows them side by side.
CREATE OR REFRESH MATERIALIZED VIEW silver_claims (
  claim_id STRING, policy_id STRING, line_of_business STRING, region STRING,
  loss_date DATE COMMENT 'Date the loss event happened.',
  report_date DATE COMMENT 'Date the claim was reported to the insurer. The daily loss ratio uses this date.',
  cause_of_loss STRING COMMENT 'Peril that caused the loss as coded by the handler (e.g. Hail, Collision, Bodily Injury).',
  incurred_loss DOUBLE COMMENT 'Paid loss plus case reserve for the claim (EUR), before recoveries.',
  paid_loss DOUBLE, case_reserve DOUBLE, claim_status STRING, currency STRING,
  event_tag STRING COMMENT 'Named event the claim belongs to, null for attritional claims.',
  large_loss_flag BOOLEAN COMMENT 'True when incurred loss is EUR 250k or more.',
  cat_event_flag BOOLEAN COMMENT 'True when the claim belongs to a catastrophe event.',
  loss_description STRING MASK ${policy_schema}.lrc_mask_free_text COMMENT 'Free text typed at first notice of loss (masked for non-PII readers).',
  genai_checked BOOLEAN COMMENT 'True when the Gen AI checks ran on this claim (the newest claims, see max_ai_claims).',
  ai_peril STRING COMMENT 'Peril inferred from the free text by ai_classify.',
  peril_consistent BOOLEAN COMMENT 'Gen AI: the coded cause of loss agrees with the peril in the description.',
  pii_detected BOOLEAN COMMENT 'Gen AI: ai_mask found personal data (names, phone numbers, emails) in the free text.',
  loss_description_masked STRING COMMENT 'Free text with personal data redacted by ai_mask.',
  source_system STRING, source_file STRING, ingested_at TIMESTAMP,
  CONSTRAINT has_claim_id                EXPECT (claim_id IS NOT NULL)            ON VIOLATION DROP ROW,
  CONSTRAINT report_not_future           EXPECT (report_date <= current_date())   ON VIOLATION DROP ROW,
  CONSTRAINT loss_before_report          EXPECT (loss_date <= report_date),
  CONSTRAINT non_negative_amount         EXPECT (incurred_loss >= 0),
  CONSTRAINT currency_is_eur             EXPECT (currency = 'EUR'),
  CONSTRAINT genai_peril_matches_text    EXPECT (peril_consistent IS NOT FALSE),
  CONSTRAINT genai_no_personal_data      EXPECT (pii_detected IS NOT TRUE)
)
WITH ROW FILTER ${policy_schema}.lrc_region_filter ON (region)
COMMENT 'Silver: one row per claim (latest version) with rule-based and Gen AI data-quality checks. Row filter by region; free text masked for non-PII readers.'
AS SELECT c.claim_id, c.policy_id, c.line_of_business, c.region, c.loss_date, c.report_date,
          c.cause_of_loss, c.incurred_loss, c.paid_loss, c.case_reserve, c.claim_status, c.currency, c.event_tag,
          c.incurred_loss >= 250000 AS large_loss_flag, c.event_tag = 'Hailstorm DACH' AS cat_event_flag,
          c.loss_description,
          g.claim_id IS NOT NULL AS genai_checked, g.ai_peril, g.peril_consistent, g.pii_detected, g.loss_description_masked,
          c.source_system, c.source_file, c.ingested_at
FROM claims_typed c
LEFT JOIN claims_genai_checks g USING (claim_id);

CREATE OR REFRESH MATERIALIZED VIEW silver_premium (
  CONSTRAINT positive_premium EXPECT (earned_premium > 0) ON VIOLATION DROP ROW,
  CONSTRAINT currency_is_eur  EXPECT (currency = 'EUR')
)
COMMENT 'Silver: earned premium per day, line of business and region from the bordereaux (latest file wins).'
AS SELECT CAST(as_of_date AS DATE) AS as_of_date, line_of_business, region, earned_premium, currency, bordereau_id, source_file
FROM bronze_premium
QUALIFY ROW_NUMBER() OVER (PARTITION BY as_of_date, line_of_business, region ORDER BY ingested_at DESC) = 1;

-- ═══ 4 · One row per issue, explained by Gen AI ═══════════════════════════════════════════════════════════════════

CREATE OR REFRESH MATERIALIZED VIEW dq_claims_issues
COMMENT 'One row per data-quality issue on the Gen AI-checked claims: Gen AI checks and rule-based checks, each with a plain-English explanation and suggested fix written by ai_query (personal data already masked).'
AS
WITH checked AS (SELECT * FROM silver_claims WHERE genai_checked),
issues AS (
  SELECT claim_id, report_date, line_of_business, region, cause_of_loss, ai_peril, incurred_loss,
         loss_description_masked, 'peril_mismatch' AS check_name, 'Gen AI' AS check_type, 'High' AS severity
  FROM checked WHERE NOT peril_consistent
  UNION ALL
  SELECT claim_id, report_date, line_of_business, region, cause_of_loss, ai_peril, incurred_loss,
         loss_description_masked, 'pii_in_free_text', 'Gen AI', 'High'
  FROM checked WHERE pii_detected
  UNION ALL
  SELECT claim_id, report_date, line_of_business, region, cause_of_loss, ai_peril, incurred_loss,
         loss_description_masked, 'negative_amount', 'Rule', 'Medium'
  FROM checked WHERE incurred_loss < 0
  UNION ALL
  SELECT claim_id, report_date, line_of_business, region, cause_of_loss, ai_peril, incurred_loss,
         loss_description_masked, 'loss_after_report', 'Rule', 'Medium'
  FROM checked WHERE loss_date > report_date
  UNION ALL
  SELECT claim_id, report_date, line_of_business, region, cause_of_loss, ai_peril, incurred_loss,
         loss_description_masked, 'non_eur_currency', 'Rule', 'Medium'
  FROM checked WHERE currency <> 'EUR'
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

-- ═══ 5 · Daily scorecard ══════════════════════════════════════════════════════════════════════════════════════════

CREATE OR REFRESH MATERIALIZED VIEW dq_daily_scorecard
COMMENT 'Daily data-quality scorecard: records checked, issues and pass rate per check (rules and Gen AI). Read by the dashboard, the Genie Agent and the Genie One brief.'
AS
WITH checked AS (
  SELECT report_date, COUNT(*) AS records_checked FROM silver_claims WHERE genai_checked GROUP BY report_date
),
issues AS (
  SELECT report_date, check_name, check_type, severity, COUNT(DISTINCT claim_id) AS issues
  FROM dq_claims_issues GROUP BY ALL
)
SELECT i.report_date, i.check_name, i.check_type, i.severity, i.issues, c.records_checked,
       ROUND(1 - i.issues / c.records_checked, 4) AS pass_rate
FROM issues i JOIN checked c USING (report_date);
