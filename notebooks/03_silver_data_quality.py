# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Pipeline, silver: Gen AI data quality, rules and governance
# MAGIC
# MAGIC Adds `pipeline/02_silver.sql` to the pipeline and runs it. In silver, **Gen AI is part of the data-quality gate**:
# MAGIC it reads the free text that rules cannot, and its verdicts are pipeline **expectations** next to the rule-based ones.
# MAGIC
# MAGIC | Check | Type | How |
# MAGIC |---|---|---|
# MAGIC | `genai_peril_matches_text` | Gen AI | `ai_classify` infers the peril from the description; the coded cause of loss must agree |
# MAGIC | `genai_no_personal_data` | Gen AI | `ai_mask` finds names, phone numbers and emails typed into the free text |
# MAGIC | `has_claim_id`, `report_not_future` | rule, drops the row | claim id present, report date not in the future |
# MAGIC | `loss_before_report`, `non_negative_amount`, `currency_is_eur` | rule, recorded | dates in order, no negative amounts, EUR only |
# MAGIC | explanation per issue | Gen AI | `ai_query` writes a two-sentence explanation and fix for every issue in `dq_claims_issues` |
# MAGIC
# MAGIC The Gen AI checks run on the newest claims only (`MAX_AI_CLAIMS`, about 2,000, in `00_setup`), which keeps the step
# MAGIC quick and the token cost bounded. Before the pipeline runs, this notebook creates the Unity Catalog row filter (each
# MAGIC claims team sees only its own region) and column mask (raw free text only for `lrc_pii_readers`) that `silver_claims`
# MAGIC attaches.

# COMMAND ----------

# MAGIC %run ./00_setup

# COMMAND ----------

# MAGIC %md ## 1 · Region access mapping (which group may see which book)

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {FQ}.lrc_region_access (group_name STRING, region STRING)
COMMENT 'Row-filter mapping for claims tables: members of group_name may see claims in region.'
""")
spark.sql(f"""
INSERT INTO {FQ}.lrc_region_access VALUES
  ('lrc_claims_uk', 'UK & Ireland'), ('lrc_claims_france', 'France'), ('lrc_claims_dach', 'DACH'),
  ('lrc_claims_southern_europe', 'Southern Europe'), ('lrc_claims_benelux', 'Benelux'),
  ('lrc_claims_all', 'UK & Ireland'), ('lrc_claims_all', 'France'), ('lrc_claims_all', 'DACH'),
  ('lrc_claims_all', 'Southern Europe'), ('lrc_claims_all', 'Benelux')
""")
display(spark.table(f"{FQ}.lrc_region_access"))

# COMMAND ----------

# MAGIC %md ## 2 · Policy functions

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {FQ}.lrc_region_filter(region STRING)
RETURNS BOOLEAN
COMMENT 'Row filter for claims tables: admins see all regions; others only regions mapped to a group they belong to.'
RETURN is_member('admins')
    OR EXISTS (SELECT 1 FROM {FQ}.lrc_region_access a
               WHERE a.region = lrc_region_filter.region AND is_account_group_member(a.group_name))
""")

spark.sql(f"""
CREATE OR REPLACE FUNCTION {FQ}.lrc_redact(s STRING)
RETURNS STRING
COMMENT 'Redacts email addresses, phone numbers and contact names from free text.'
RETURN regexp_replace(regexp_replace(regexp_replace(s,
         '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\\\.[A-Za-z]{{2,}}', '[email]'),
         '\\\\+?[0-9][0-9 ]{{7,}}[0-9]', '[phone]'),
         '([Cc]ontact|[Cc]all|[Aa]sk for|[Ss]peak to) [A-Z][a-z]+( [A-Z][A-Za-z\\']+)?', '$1 [name]')
""")

spark.sql(f"""
CREATE OR REPLACE FUNCTION {FQ}.lrc_mask_free_text(s STRING)
RETURNS STRING
COMMENT 'Column mask for claim free text: raw text for admins and lrc_pii_readers, redacted for everyone else.'
RETURN CASE WHEN is_member('admins') OR is_account_group_member('lrc_pii_readers') THEN s ELSE {FQ}.lrc_redact(s) END
""")
print("policy functions ready")

# COMMAND ----------

# MAGIC %md ## 3 · Add `pipeline/02_silver.sql` to the pipeline and run it

# COMMAND ----------

# MAGIC %run ./_pipeline

# COMMAND ----------

run_pipeline(["bronze", "silver"])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4 · Gen AI and rule expectations, side by side
# MAGIC The pipeline records every expectation in its event log. The Gen AI checks appear next to the rules, and you can
# MAGIC see the same numbers on the pipeline's **Data quality** tab.

# COMMAND ----------

display(spark.sql(f"""
  SELECT e.dataset, e.name AS expectation,
         IF(e.name LIKE 'genai_%', 'Gen AI', 'Rule') AS check_type,
         SUM(e.passed_records) AS passed, SUM(e.failed_records) AS failed,
         ROUND(SUM(e.passed_records) / NULLIF(SUM(e.passed_records) + SUM(e.failed_records), 0), 4) AS pass_rate
  FROM (SELECT explode(from_json(details:flow_progress:data_quality:expectations,
                       'ARRAY<STRUCT<name: STRING, dataset: STRING, passed_records: BIGINT, failed_records: BIGINT>>')) AS e
        FROM event_log('{get_setting("pipeline_id")}')
        WHERE event_type = 'flow_progress' AND origin.update_id = '{LAST_UPDATE_ID}'
          AND details:flow_progress:data_quality:expectations IS NOT NULL)
  GROUP BY ALL ORDER BY check_type, expectation"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5 · What Gen AI found in the free text

# COMMAND ----------

display(spark.sql(f"""
  SELECT COUNT(*) AS claims_in_silver, COUNT_IF(genai_checked) AS checked_by_gen_ai,
         COUNT_IF(NOT peril_consistent) AS cause_code_contradicts_text, COUNT_IF(pii_detected) AS personal_data_in_text
  FROM {FQ}.silver_claims"""))
display(spark.sql(f"""
  SELECT check_name, claim_id, line_of_business, region, cause_of_loss AS coded_cause, ai_peril AS peril_in_text,
         loss_description_masked, ai_explanation
  FROM {FQ}.dq_claims_issues WHERE check_type = 'Gen AI' LIMIT 10"""))
display(spark.sql(f"""
  SELECT check_name, check_type, SUM(issues) AS claims_with_issue, ROUND(AVG(pass_rate), 4) AS avg_pass_rate
  FROM {FQ}.dq_daily_scorecard GROUP BY ALL ORDER BY claims_with_issue DESC"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6 · What the policies do
# MAGIC Left: the raw text an authorised reader sees. Right: what any other analyst, Genie user or report sees.

# COMMAND ----------

if spark.catalog.tableExists(f"{CATALOG}.{SCHEMA}.silver_claims"):
    display(spark.sql(f"""
      SELECT claim_id, region, loss_description AS seen_by_pii_readers, {FQ}.lrc_redact(loss_description) AS seen_by_everyone_else
      FROM {FQ}.silver_claims WHERE loss_description RLIKE '@|\\\\+44' LIMIT 8"""))
    display(spark.sql(f"""
      SELECT a.group_name, COUNT(*) AS claims_visible
      FROM {FQ}.silver_claims c JOIN {FQ}.lrc_region_access a ON a.region = c.region
      GROUP BY a.group_name ORDER BY a.group_name"""))

# COMMAND ----------

# MAGIC %md ## 7 · Policies attached in Unity Catalog

# COMMAND ----------

for t in ["silver_claims"]:
    if spark.catalog.tableExists(f"{CATALOG}.{SCHEMA}.{t}"):
        rows = [r for r in spark.sql(f"DESCRIBE TABLE EXTENDED {FQ}.{t}").collect()
                if any(k in (r[0] or "") for k in ("Row Filter", "Column Mask", "Masks", "Filter"))]
        print(t, [(r[0], r[1]) for r in rows] or "(policies are attached when the pipeline next refreshes)")
