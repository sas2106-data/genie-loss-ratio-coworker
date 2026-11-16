# Databricks notebook source
# MAGIC %md
# MAGIC # Gen AI 04 · How good are the Gen AI data-quality checks?
# MAGIC
# MAGIC The landing notebook (`src/raw/03_land_raw_files.py`) seeds known defects into the raw files, so every Gen AI
# MAGIC finding can be scored against ground truth:
# MAGIC
# MAGIC | Check (Lakeflow pipeline) | Gen AI function | Ground truth |
# MAGIC |---|---|---|
# MAGIC | `peril_mismatch` | `ai_classify` reads the free-text description and infers the peril | coded `cause_of_loss` in the file differs from the source system (`claims`) |
# MAGIC | `pii_in_free_text` | `ai_mask` redacts names, phone numbers and emails | the description contains the seeded contact details |
# MAGIC
# MAGIC Output: precision, recall and F1 per check in `dq_genai_eval` (appended per run), plus the misses and false alarms
# MAGIC to inspect. This is what a data-quality owner needs before trusting an LLM in a production pipeline.

# COMMAND ----------

dbutils.widgets.text("catalog", "")
dbutils.widgets.text("schema", "loss_ratio_coworker")
CATALOG = dbutils.widgets.get("catalog") or spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = dbutils.widgets.get("schema")
FQ = f"`{CATALOG}`.`{SCHEMA}`"

# COMMAND ----------

# MAGIC %md ## Ground truth vs Gen AI flags, claim by claim

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TEMP VIEW genai_scored AS
SELECT a.claim_id, a.report_date, a.cause_of_loss AS coded_cause, c.cause_of_loss AS source_cause, a.ai_peril,
       a.loss_description, a.loss_description_masked,
       a.cause_of_loss <> c.cause_of_loss                                   AS truth_peril_mismatch,
       NOT a.peril_consistent                                               AS flag_peril_mismatch,
       a.loss_description RLIKE '@example\\\\.com|\\\\+44 7700'             AS truth_pii,
       a.pii_detected                                                       AS flag_pii
FROM {FQ}.silver_claims_ai_checked a
JOIN {FQ}.claims c USING (claim_id)
""")
display(spark.sql("SELECT * EXCEPT (loss_description) FROM genai_scored WHERE truth_peril_mismatch OR flag_peril_mismatch OR truth_pii OR flag_pii LIMIT 50"))

# COMMAND ----------

# MAGIC %md ## Precision, recall, F1

# COMMAND ----------

ev = spark.sql(f"""
WITH m AS (
  SELECT 'peril_mismatch' AS check_name, 'ai_classify' AS genai_function, truth_peril_mismatch AS t, flag_peril_mismatch AS f FROM genai_scored
  UNION ALL
  SELECT 'pii_in_free_text', 'ai_mask', truth_pii, flag_pii FROM genai_scored
)
SELECT current_timestamp() AS evaluated_at, check_name, genai_function, COUNT(*) AS claims_checked,
       SUM(CAST(t AS INT)) AS seeded_defects,
       SUM(CAST(f AS INT)) AS flagged,
       SUM(CAST(t AND f AS INT)) AS true_positives,
       SUM(CAST(f AND NOT t AS INT)) AS false_positives,
       SUM(CAST(t AND NOT f AS INT)) AS false_negatives,
       ROUND(SUM(CAST(t AND f AS INT)) / NULLIF(SUM(CAST(f AS INT)), 0), 3) AS precision,
       ROUND(SUM(CAST(t AND f AS INT)) / NULLIF(SUM(CAST(t AS INT)), 0), 3) AS recall
FROM m GROUP BY check_name, genai_function
""")
ev = ev.selectExpr("*", "ROUND(2 * precision * recall / NULLIF(precision + recall, 0), 3) AS f1")
ev.write.mode("append").option("mergeSchema", "true").saveAsTable(f"{FQ}.dq_genai_eval")
spark.sql(f"COMMENT ON TABLE {FQ}.dq_genai_eval IS 'Precision/recall of the Gen AI data-quality checks (ai_classify, ai_mask) against seeded defects, one row per check per run.'")
display(ev)

# COMMAND ----------

# MAGIC %md ## Misses and false alarms (what to tune)
# MAGIC False alarms on `peril_mismatch` are usually narratives that fit two perils (e.g. a storm that caused water
# MAGIC damage); tune the label list or the peril → cause mapping in the pipeline rather than the threshold.

# COMMAND ----------

display(spark.sql("""
SELECT 'peril false alarm' AS kind, claim_id, coded_cause, ai_peril, loss_description_masked FROM genai_scored WHERE flag_peril_mismatch AND NOT truth_peril_mismatch
UNION ALL
SELECT 'peril miss', claim_id, coded_cause, ai_peril, loss_description_masked FROM genai_scored WHERE truth_peril_mismatch AND NOT flag_peril_mismatch
UNION ALL
SELECT 'pii miss', claim_id, coded_cause, ai_peril, loss_description_masked FROM genai_scored WHERE truth_pii AND NOT flag_pii
LIMIT 30
"""))
