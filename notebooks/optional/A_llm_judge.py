# Databricks notebook source
# MAGIC %md
# MAGIC # Optional A · LLM judge: grade the Genie explanations from the daily watch
# MAGIC
# MAGIC **Optional: the main flow does not need it.** Run it any time after step 06.
# MAGIC
# MAGIC `ai_query` asks an independent model (`JUDGE_ENDPOINT` in `00_config`) to grade every Genie explanation stored in
# MAGIC `lr_alerts`: are the numbers grounded in the facts, does it name the driver, is it actionable? The verdicts are
# MAGIC appended to `lr_explanation_judge`, so explanation quality is tracked over time instead of assumed.

# COMMAND ----------

# MAGIC %run ../00_config

# COMMAND ----------

judged = spark.sql(f"""
WITH today AS (
  SELECT alert_id, line_of_business, region, status, primary_driver, lr_7d, target_loss_ratio, genie_explanation
  FROM {FQ}.lr_alerts WHERE as_of_date = (SELECT MAX(as_of_date) FROM {FQ}.lr_alerts) AND genie_explanation IS NOT NULL
),
j AS (
  SELECT *, ai_query('{JUDGE}', concat(
    'You audit explanations written by an analytics assistant for insurance executives. Reply with JSON only: ',
    '{{"grounded": true|false, "names_driver": true|false, "actionable": true|false, "score": 1-5, "reason": "<max 20 words>"}}. ',
    'grounded: its numbers agree with the FACTS. names_driver: it identifies the driver given in the FACTS. ',
    'actionable: an executive knows what to look at next. ',
    'FACTS: segment ', line_of_business, ' / ', region, ', status ', status, ', 7-day loss ratio ', cast(round(lr_7d * 100, 1) AS STRING),
    '%, target ', cast(round(target_loss_ratio * 100, 1) AS STRING), '%, driver ', primary_driver,
    '. EXPLANATION: ', genie_explanation)) AS verdict_raw
  FROM today
)
SELECT current_timestamp() AS judged_at, '{JUDGE}' AS judge_endpoint, alert_id, line_of_business, region, primary_driver,
       from_json(regexp_extract(verdict_raw, '[{{].*[}}]', 0),
                 'grounded BOOLEAN, names_driver BOOLEAN, actionable BOOLEAN, score INT, reason STRING') AS v
FROM j
""").selectExpr("judged_at", "judge_endpoint", "alert_id", "line_of_business", "region", "primary_driver", "v.*")
judged.write.mode("append").option("mergeSchema", "true").saveAsTable(f"{FQ}.lr_explanation_judge")
spark.sql(f"COMMENT ON TABLE {FQ}.lr_explanation_judge IS 'LLM-judge verdicts on the Genie explanations stored in lr_alerts, appended every run.'")
display(judged.select("alert_id", "primary_driver", "grounded", "names_driver", "actionable", "score", "reason"))
display(spark.sql(f"""SELECT date(judged_at) AS day, COUNT(*) AS explanations, ROUND(AVG(score), 2) AS avg_score,
                             ROUND(AVG(CAST(grounded AS INT)), 2) AS grounded, ROUND(AVG(CAST(names_driver AS INT)), 2) AS names_driver
                      FROM {FQ}.lr_explanation_judge GROUP BY ALL ORDER BY day"""))

# COMMAND ----------
