# Databricks notebook source
# MAGIC %md
# MAGIC # Optional · Ask the Genie Agent why, then grade its answers with an LLM judge
# MAGIC
# MAGIC **Optional module: the main flow does not need it.** Run it any time after step 06.
# MAGIC
# MAGIC 1. For each RED or AMBER segment, ask the Loss Ratio Coworker Genie Agent *why* through the **Genie Conversation API**
# MAGIC    and store the answer in `lr_alerts`.
# MAGIC 2. `ai_query` asks an independent model (`JUDGE_ENDPOINT`) to grade each answer: grounded in the numbers, names the
# MAGIC    driver, actionable. The verdicts are appended to `lr_explanation_judge`, so explanation quality is tracked over time.

# COMMAND ----------

# MAGIC %run ../00_setup

# COMMAND ----------

import time
import pandas as pd
from databricks.sdk import WorkspaceClient
from pyspark.sql import functions as F

w = WorkspaceClient()
assert SPACE_ID, "Run step 06 first: it creates the Genie Agent"

def ask_genie(question):
    """Genie Conversation API over REST."""
    try:
        base = f"/api/2.0/genie/spaces/{SPACE_ID}"
        start = w.api_client.do("POST", f"{base}/start-conversation", body={"content": question})
        cid, mid = start["conversation_id"], start["message_id"]
        for _ in range(60):
            msg = w.api_client.do("GET", f"{base}/conversations/{cid}/messages/{mid}")
            if msg.get("status") in ("COMPLETED", "FAILED", "CANCELLED"):
                break
            time.sleep(3)
        atts = msg.get("attachments") or []
        parts = [a["text"]["content"] for a in atts if a.get("text", {}).get("content")]
        return "\n".join(parts).strip()
    except Exception as e:
        return f"(Genie explanation unavailable: {e})"

watch = spark.sql(f"SELECT * FROM {FQ}.v_loss_ratio_watchlist WHERE status IN ('RED', 'AMBER')").toPandas()
alerts = []
for r in watch.itertuples():
    q = (f"Why did the {r.line_of_business} loss ratio in {r.region} rise over the last 7 days? Split it into claim "
         f"frequency versus severity, list the top causes of loss and any large or catastrophe losses, and compare it "
         f"with the target loss ratio. Answer in three short bullet points.")
    alerts.append(dict(alert_id=f"LR-{r.as_of_date:%Y%m%d}-{r.line_of_business[:3].upper()}-{r.region.split()[0][:4].upper()}",
                       as_of_date=r.as_of_date, line_of_business=r.line_of_business, region=r.region, status=r.status,
                       primary_driver=r.primary_driver, lr_7d=float(r.lr_7d), target_loss_ratio=float(r.target_loss_ratio),
                       genie_explanation=ask_genie(q)))
if alerts:
    (spark.createDataFrame(pd.DataFrame(alerts)).withColumn("created_at", F.current_timestamp())
         .write.mode("append").option("mergeSchema", "true").saveAsTable(f"{FQ}.lr_alerts"))
display(spark.createDataFrame(pd.DataFrame(alerts)).select("alert_id", "primary_driver", "genie_explanation") if alerts else spark.sql("SELECT 'no RED or AMBER segments today' AS note"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## LLM judge

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
