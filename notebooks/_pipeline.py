# Databricks notebook source
# MAGIC %md
# MAGIC # Pipeline helper (`%run ./_pipeline`)
# MAGIC
# MAGIC Steps 02, 03 and 04 grow **one** Lakeflow Spark Declarative Pipeline layer by layer: each step adds its SQL file from
# MAGIC `pipeline/` to the pipeline's source code, runs an update and waits for it to finish.

# COMMAND ----------

import time
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
LAYERS = {"bronze": "01_bronze.sql", "silver": "02_silver.sql", "gold": "03_gold.sql"}


def run_pipeline(layers):
    spec = {
        "name": f"[LRC] Loss ratio pipeline · {CATALOG}.{SCHEMA}",
        "catalog": CATALOG, "schema": SCHEMA, "serverless": True, "photon": True, "channel": "CURRENT",
        "libraries": [{"file": {"path": f"{repo_root()}/pipeline/{LAYERS[l]}"}} for l in layers],
        "configuration": {"raw_path": RAW, "policy_schema": f"{CATALOG}.{SCHEMA}", "llm_endpoint": LLM_ENDPOINT,
                          "ai_lookback_days": str(AI_LOOKBACK_DAYS), "max_ai_claims": str(MAX_AI_CLAIMS)},
    }
    pid = get_setting("pipeline_id")
    if pid:
        try:
            w.api_client.do("PUT", f"/api/2.0/pipelines/{pid}", body={**spec, "id": pid})
        except Exception:
            pid = ""
    if not pid:
        pid = w.api_client.do("POST", "/api/2.0/pipelines", body=spec)["pipeline_id"]
        save_setting("pipeline_id", pid)
    print(f"pipeline {pid} with source code: {', '.join(LAYERS[l] for l in layers)}")
    print(f"watch it run: {w.config.host}/pipelines/{pid}")
    update_id = w.api_client.do("POST", f"/api/2.0/pipelines/{pid}/updates", body={"full_refresh": FULL_REFRESH})["update_id"]
    state = ""
    for _ in range(160):
        state = w.api_client.do("GET", f"/api/2.0/pipelines/{pid}/updates/{update_id}")["update"]["state"]
        if state in ("COMPLETED", "FAILED", "CANCELED"):
            break
        time.sleep(15)
    global LAST_UPDATE_ID
    LAST_UPDATE_ID = update_id
    print(f"update {update_id}: {state}")
    assert state == "COMPLETED", "Open the pipeline link above to see which table failed"
    return pid
