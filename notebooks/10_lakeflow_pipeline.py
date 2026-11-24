# Databricks notebook source
# MAGIC %md
# MAGIC # 10 · Lakeflow pipeline: raw files → bronze → silver → Gen AI data quality → gold
# MAGIC
# MAGIC Creates (or updates) a serverless **Lakeflow Spark Declarative Pipeline** from `pipeline/lrc_ingest_pipeline.sql`
# MAGIC in this Git folder, runs one update and waits for it. Open the SQL file to read the pipeline:
# MAGIC
# MAGIC | Layer | Tables | What happens |
# MAGIC |---|---|---|
# MAGIC | Bronze | `bronze_fnol`, `bronze_premium` | Auto Loader (`read_files` stream) picks up the files from step 09 |
# MAGIC | Silver | `silver_claims`, `silver_premium` | expectations (EUR only, no negatives, valid dates), de-duplication; the row filter and column mask from step 02 |
# MAGIC | Gen AI | `silver_claims_ai_checked`, `dq_claims_issues`, `dq_daily_scorecard` | `ai_classify` peril vs coded cause, `ai_mask` personal data, `ai_query` explains each issue |
# MAGIC | Gold | `gold_daily_loss_run_lf`, `gold_rate_adequacy` | loss run from the files; rate adequacy with the Lakebase pricing snapshots from step 08 |
# MAGIC
# MAGIC Needs steps 02, 08 and 09 first. The first run takes about 5 to 10 minutes.

# COMMAND ----------

# MAGIC %run ./00_config

# COMMAND ----------

import time
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
spec = {
    "name": f"[LRC] Lakeflow ingest · {CATALOG}.{SCHEMA}",
    "catalog": CATALOG, "schema": SCHEMA, "serverless": True, "photon": True, "channel": "CURRENT",
    "libraries": [{"file": {"path": f"{repo_root()}/pipeline/lrc_ingest_pipeline.sql"}}],
    "configuration": {"raw_path": f"/Volumes/{CATALOG}/{SCHEMA}/raw", "llm_endpoint": LLM_ENDPOINT,
                      "ai_lookback_days": str(AI_LOOKBACK_DAYS), "policy_schema": f"{CATALOG}.{SCHEMA}"},
}
pid = get_setting("pipeline_id")
if pid:
    try:
        w.api_client.do("PUT", f"/api/2.0/pipelines/{pid}", body={**spec, "id": pid})
        print(f"updated pipeline {pid}")
    except Exception:
        pid = ""
if not pid:
    pid = w.api_client.do("POST", "/api/2.0/pipelines", body=spec)["pipeline_id"]
    save_setting("pipeline_id", pid)
    print(f"created pipeline {pid}")
print(f"{w.config.host}/pipelines/{pid}")

# COMMAND ----------

update_id = w.api_client.do("POST", f"/api/2.0/pipelines/{pid}/updates", body={"full_refresh": False})["update_id"]
state = ""
for _ in range(120):
    state = w.api_client.do("GET", f"/api/2.0/pipelines/{pid}/updates/{update_id}")["update"]["state"]
    if state in ("COMPLETED", "FAILED", "CANCELED"):
        break
    time.sleep(15)
print(f"pipeline update {update_id}: {state}")
assert state == "COMPLETED", "Open the pipeline link above to see which table failed"

# COMMAND ----------

# MAGIC %md ## What the pipeline found

# COMMAND ----------

display(spark.sql(f"""
  SELECT check_name, check_type, SUM(issues) AS issues, ROUND(AVG(pass_rate), 4) AS avg_pass_rate
  FROM {FQ}.dq_daily_scorecard GROUP BY ALL ORDER BY issues DESC"""))
display(spark.sql(f"""
  SELECT (SELECT COUNT(*) FROM {FQ}.bronze_fnol) AS bronze_records, (SELECT COUNT(*) FROM {FQ}.silver_claims) AS silver_claims,
         (SELECT COUNT(DISTINCT claim_id) FROM {FQ}.dq_claims_issues) AS claims_with_issues"""))
