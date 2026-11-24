-- Lakeflow Spark Declarative Pipeline · GOLD (added by notebooks/04_gold)
--
-- The daily loss run per line of business and region: incurred loss on the date reported and earned premium.
-- One governed table that the metric views, Genie, the dashboard and the app all read.

-- ═══ GOLD: the daily loss run from the governed pipeline ═════════════════════════════════════════════════════════

CREATE OR REFRESH MATERIALIZED VIEW gold_daily_loss_run (
  as_of_date DATE COMMENT 'Report date (the day losses hit the books).',
  line_of_business STRING, region STRING,
  earned_premium DOUBLE COMMENT 'Premium earned on the day (EUR).',
  incurred_loss DOUBLE COMMENT 'Incurred loss reported on the day (EUR).',
  paid_loss DOUBLE, case_reserve DOUBLE, claim_count BIGINT, large_loss_incurred DOUBLE, large_loss_count BIGINT, cat_incurred DOUBLE
)
COMMENT 'Gold: incurred loss on the date reported and earned premium per day × line of business × region. The metric views read this table. Claims with a negative amount or non-EUR currency are excluded until fixed.'
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
