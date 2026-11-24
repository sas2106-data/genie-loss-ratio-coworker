# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Pipeline, silver: data-quality rules, governance and Gen AI checks
# MAGIC
# MAGIC Adds `pipeline/02_silver.sql` to the pipeline and runs it. Before that, this notebook creates the Unity Catalog
# MAGIC policy functions that the silver tables attach.
# MAGIC
# MAGIC | What | How | Where you see it |
# MAGIC |---|---|---|
# MAGIC | Rule-based data quality | **expectations**: claim id present, report date not in the future, loss before report, no negative amounts, EUR only; de-duplication of resent claims | pipeline graph (expectation pass rates), `silver_claims`, `silver_premium` |
# MAGIC | Governance | **row filter** by region (`lrc_region_filter`), **column mask** on the free text (`lrc_mask_free_text`) | `silver_claims` |
# MAGIC | Gen AI data quality | `ai_classify` peril vs coded cause, `ai_mask` personal data, `ai_query` explains each issue and the fix, on at most `MAX_AI_CLAIMS` recent claims | `silver_claims_ai_checked`, `dq_claims_issues`, `dq_daily_scorecard` |

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
# MAGIC ## 4 · What the data-quality checks found

# COMMAND ----------

display(spark.sql(f"""
  SELECT check_name, check_type, SUM(issues) AS claims_with_issue, ROUND(AVG(pass_rate), 4) AS avg_pass_rate
  FROM {FQ}.dq_daily_scorecard GROUP BY ALL ORDER BY claims_with_issue DESC"""))
display(spark.sql(f"""
  SELECT check_name, claim_id, line_of_business, region, cause_of_loss, ai_peril, ai_explanation
  FROM {FQ}.dq_claims_issues WHERE check_type = 'Gen AI' LIMIT 10"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5 · What the policies do
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

# MAGIC %md ## 6 · Policies attached in Unity Catalog

# COMMAND ----------

for t in ["silver_claims", "silver_claims_ai_checked"]:
    if spark.catalog.tableExists(f"{CATALOG}.{SCHEMA}.{t}"):
        rows = [r for r in spark.sql(f"DESCRIBE TABLE EXTENDED {FQ}.{t}").collect()
                if any(k in (r[0] or "") for k in ("Row Filter", "Column Mask", "Masks", "Filter"))]
        print(t, [(r[0], r[1]) for r in rows] or "(policies are attached when the pipeline next refreshes)")
