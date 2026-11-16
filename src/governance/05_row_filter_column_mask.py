# Databricks notebook source
# MAGIC %md
# MAGIC # Governance 05 · Row filter by region and column mask on claim free text (Unity Catalog)
# MAGIC
# MAGIC The Lakeflow pipeline attaches these policies to the claims tables it publishes
# MAGIC (`silver_claims`, `silver_claims_ai_checked`, see `src/pipeline/lrc_ingest_pipeline.sql`):
# MAGIC
# MAGIC | Policy | Function | Effect |
# MAGIC |---|---|---|
# MAGIC | **Row filter** on `region` | `lrc_region_filter(region)` | A claims team sees only its own book: membership of a group listed in `lrc_region_access` for that region. Workspace admins (the pipeline owner) see all regions. |
# MAGIC | **Column mask** on `loss_description` | `lrc_mask_free_text(s)` | GDPR: only members of `lrc_pii_readers` (and admins) see the raw text; everyone else sees it with emails, phone numbers and contact names redacted by `lrc_redact`. |
# MAGIC
# MAGIC Gen AI (`ai_mask`) finds personal data the regexes miss, such as names. The column mask *enforces* redaction for
# MAGIC every query, on every surface (SQL, Genie, dashboards, Power BI DirectQuery), regardless of who wrote the query.
# MAGIC
# MAGIC This notebook runs before the pipeline in the `lrc_end_to_end` job, because the pipeline references the functions.

# COMMAND ----------

dbutils.widgets.text("catalog", "")
dbutils.widgets.text("schema", "loss_ratio_coworker")
CATALOG = dbutils.widgets.get("catalog") or spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = dbutils.widgets.get("schema")
FQ = f"`{CATALOG}`.`{SCHEMA}`"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {FQ}")

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

# MAGIC %md ## 3 · What the policies do (evidence)
# MAGIC Left: the raw text an authorised reader sees. Right: what any other analyst, Genie user or Power BI report sees.

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

# MAGIC %md ## 4 · Policies attached in Unity Catalog

# COMMAND ----------

for t in ["silver_claims", "silver_claims_ai_checked"]:
    if spark.catalog.tableExists(f"{CATALOG}.{SCHEMA}.{t}"):
        rows = [r for r in spark.sql(f"DESCRIBE TABLE EXTENDED {FQ}.{t}").collect()
                if any(k in (r[0] or "") for k in ("Row Filter", "Column Mask", "Masks", "Filter"))]
        print(t, [(r[0], r[1]) for r in rows] or "(policies are attached when the pipeline next refreshes)")
