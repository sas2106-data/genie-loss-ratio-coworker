# Databricks notebook source
# MAGIC %md
# MAGIC # Optional · How good are the Gen AI data-quality checks? (precision, recall, LLM judge)
# MAGIC
# MAGIC **Optional: the main flow does not need it.** Run it any time after step 03.
# MAGIC
# MAGIC Step 01 plants known defects into the raw files, so every Gen AI
# MAGIC finding can be scored against ground truth:
# MAGIC
# MAGIC | Check (Lakeflow pipeline) | Gen AI function | Ground truth |
# MAGIC |---|---|---|
# MAGIC | `peril_mismatch` | `ai_classify` reads the free-text description and infers the peril | coded `cause_of_loss` in the file differs from the source system (`truth_claims`, written by step 01) |
# MAGIC | `pii_in_free_text` | `ai_mask` redacts names, phone numbers and emails | the description contains the seeded contact details |
# MAGIC
# MAGIC A second, independent model family then acts as an **LLM judge** of the `ai_query` explanations (step 4).
# MAGIC
# MAGIC Output: precision, recall and F1 per check in `dq_genai_eval` (appended per run), plus the misses and false alarms
# MAGIC to inspect. This is what a data-quality owner needs before trusting an LLM in a production pipeline.

# COMMAND ----------

# MAGIC %run ../00_setup

# COMMAND ----------

SAMPLE = 40  # explanations graded by the LLM judge

# COMMAND ----------

# MAGIC %md ## Ground truth vs Gen AI flags, claim by claim

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TEMP VIEW genai_scored AS
SELECT a.claim_id, a.report_date, a.cause_of_loss AS coded_cause, c.cause_of_loss AS source_cause, a.ai_peril,
       s.loss_description, a.loss_description_masked,
       a.cause_of_loss <> c.cause_of_loss                                   AS truth_peril_mismatch,
       NOT a.peril_consistent                                               AS flag_peril_mismatch,
       s.loss_description RLIKE '@example\\\\.com|\\\\+44 7700'             AS truth_pii,
       a.pii_detected                                                       AS flag_pii
FROM {FQ}.silver_claims_ai_checked a
JOIN {FQ}.truth_claims c USING (claim_id)
JOIN {FQ}.silver_claims s USING (claim_id)
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

# COMMAND ----------

# MAGIC %md ## LLM judge: are the ai_query explanations right, actionable and safe?
# MAGIC The explanations are written by the pipeline's model (Llama 3.3 70B). A different model family judges a sample of
# MAGIC them on four criteria, so the generator is not grading itself. Results are appended to `dq_explanation_judge`.

# COMMAND ----------

judged = spark.sql(f"""
WITH s AS (
  SELECT claim_id, check_name, cause_of_loss, ai_peril, loss_description_masked, ai_explanation
  FROM {FQ}.dq_claims_issues ORDER BY hash(claim_id, check_name) LIMIT {SAMPLE}
),
j AS (
  SELECT *, ai_query('{JUDGE}', concat(
    'You are auditing an automated claims data-quality assistant. Judge the EXPLANATION below. ',
    'Reply with JSON only, no prose: {{"correct_check": true|false, "actionable": true|false, "no_personal_data": true|false, ',
    '"faithful": true|false, "score": 1-5, "reason": "<max 20 words>"}}. ',
    'correct_check: it explains the failed check named. actionable: it tells a claims handler what to change. ',
    'no_personal_data: it contains no names, phone numbers or emails. faithful: it invents no facts beyond the inputs. ',
    'CHECK: ', check_name, '. CODED CAUSE: ', coalesce(cause_of_loss, 'n/a'), '. AI PERIL: ', coalesce(ai_peril, 'n/a'),
    '. DESCRIPTION (masked): ', coalesce(loss_description_masked, ''), '. EXPLANATION: ', ai_explanation)) AS verdict_raw
  FROM s
)
SELECT current_timestamp() AS judged_at, '{JUDGE}' AS judge_endpoint, claim_id, check_name, ai_explanation,
       from_json(regexp_extract(verdict_raw, '[{{].*[}}]', 0),
                 'correct_check BOOLEAN, actionable BOOLEAN, no_personal_data BOOLEAN, faithful BOOLEAN, score INT, reason STRING') AS v
FROM j
""").selectExpr("judged_at", "judge_endpoint", "claim_id", "check_name", "ai_explanation", "v.*")
judged.write.mode("append").option("mergeSchema", "true").saveAsTable(f"{FQ}.dq_explanation_judge")
spark.sql(f"COMMENT ON TABLE {FQ}.dq_explanation_judge IS 'LLM-judge verdicts on ai_query data-quality explanations (independent model family), appended per run.'")
latest = f"(SELECT * FROM {FQ}.dq_explanation_judge WHERE judged_at = (SELECT MAX(judged_at) FROM {FQ}.dq_explanation_judge))"
display(spark.sql(f"""
SELECT check_name, COUNT(*) AS judged,
       ROUND(AVG(CAST(correct_check AS INT)), 3) AS correct_check, ROUND(AVG(CAST(actionable AS INT)), 3) AS actionable,
       ROUND(AVG(CAST(no_personal_data AS INT)), 3) AS no_personal_data, ROUND(AVG(CAST(faithful AS INT)), 3) AS faithful,
       ROUND(AVG(score), 2) AS avg_score
FROM {latest} GROUP BY ROLLUP (check_name) ORDER BY check_name NULLS LAST"""))
display(spark.sql(f"SELECT check_name, score, reason, ai_explanation FROM {latest} WHERE score <= 3 OR NOT faithful LIMIT 10"))
