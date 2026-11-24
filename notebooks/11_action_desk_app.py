# Databricks notebook source
# MAGIC %md
# MAGIC # 11 · Databricks App on Lakebase: the Action Desk
# MAGIC
# MAGIC Deploys the Streamlit app in `app/action_desk/` (in this Git folder). Team leads acknowledge, own and close the
# MAGIC actions published in step 10; the pricing desk approves or rejects proposed rate actions. Every change is a Postgres
# MAGIC transaction in Lakebase, which step 12 copies back into Delta.
# MAGIC
# MAGIC The app reads `LAKEBASE_INSTANCE` and `LRC_SCHEMA` from `app/action_desk/app.yaml`: keep them in line with `00_setup`.

# COMMAND ----------

# MAGIC %pip install -q "databricks-sdk>=0.65" "psycopg[binary]>=3.2"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ./00_setup

# COMMAND ----------

# MAGIC %run ./_lakebase_conn

# COMMAND ----------

import time

try:
    w.api_client.do("GET", f"/api/2.0/apps/{APP_NAME}")
    print(f"app {APP_NAME} exists")
except Exception:
    w.api_client.do("POST", "/api/2.0/apps", body={
        "name": APP_NAME, "description": "Loss Ratio Action Desk: team actions, watchlist and rate actions on Lakebase",
        "resources": [{"name": "lakebase", "description": "Lakebase operational store",
                       "database": {"instance_name": LAKEBASE_INSTANCE, "database_name": LAKEBASE_DATABASE,
                                    "permission": "CAN_CONNECT_AND_CREATE"}}]})
    print(f"creating app {APP_NAME}, 2 to 5 minutes …")
for _ in range(60):
    app = w.api_client.do("GET", f"/api/2.0/apps/{APP_NAME}")
    if app.get("compute_status", {}).get("state") == "ACTIVE":
        break
    time.sleep(15)
print(f"app compute: {app.get('compute_status', {}).get('state')}")

# COMMAND ----------

dep = w.api_client.do("POST", f"/api/2.0/apps/{APP_NAME}/deployments",
                      body={"source_code_path": f"{repo_root()}/app/action_desk"})
for _ in range(60):
    st = w.api_client.do("GET", f"/api/2.0/apps/{APP_NAME}/deployments/{dep['deployment_id']}")["status"]
    if st["state"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
        break
    time.sleep(10)
print(f"deployment: {st['state']} {st.get('message', '')}")
assert st["state"] == "SUCCEEDED"

# COMMAND ----------

# MAGIC %md ## Give the app's service principal access to the Postgres tables

# COMMAND ----------

grant_app(ensure_instance(LAKEBASE_INSTANCE), LAKEBASE_DATABASE, APP_NAME, SCHEMA)
print(f"Open the app: {app.get('url')}")
