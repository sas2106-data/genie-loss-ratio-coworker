# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Settings (every other notebook runs this first)
# MAGIC
# MAGIC Set the values in the next cell **once**. Every step notebook starts with `%run ./00_config`, so they all
# MAGIC write to the same catalog and schema. You don't need to run this notebook on its own.
# MAGIC
# MAGIC | Setting | What it is |
# MAGIC |---|---|
# MAGIC | `CATALOG` | an existing Unity Catalog catalog where you can create a schema |
# MAGIC | `SCHEMA` | the schema the tutorial creates (tables, views, the raw volume and the model all live here) |
# MAGIC | `WAREHOUSE_ID` | serverless SQL warehouse for the Genie Agent and the dashboard; blank = the first serverless warehouse |
# MAGIC | `LAKEBASE_*`, `APP_NAME` | Lakebase Postgres instance, its database and the Action Desk app. If you change them, change `app/action_desk/app.yaml` too |
# MAGIC | `LLM_ENDPOINT` | model used by `ai_query` inside the Lakeflow pipeline |
# MAGIC | `MAX_RAW_CLAIMS` | cap on the claims landed as raw files for the pipeline and its Gen AI checks (keeps step 10 quick and cheap) |
# MAGIC | `DRY_RUN` | the daily watch prints the Slack and Teams cards instead of sending them |
# MAGIC | `JUDGE_ENDPOINT` | used only by the optional notebooks |

# COMMAND ----------

CATALOG = "main"                          # <-- change to your catalog
SCHEMA = "loss_ratio_coworker"
WAREHOUSE_ID = ""                         # blank = first serverless SQL warehouse found

LAKEBASE_INSTANCE = "lrc-lakebase"
LAKEBASE_DATABASE = "lrc_ops"
APP_NAME = "lrc-action-desk"

LLM_ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"
AI_LOOKBACK_DAYS = 14                     # report days covered by the Gen AI checks in the pipeline
MAX_RAW_CLAIMS = 2000                     # about 2,000 claims land as raw files
MAX_RAW_DAYS = 30
FILES_PER_DAY = 2

DRY_RUN = True
SECRET_SCOPE = "loss_ratio_coworker"      # only needed with DRY_RUN = False (keys slack_webhook_url, teams_webhook_url)
JUDGE_ENDPOINT = "databricks-claude-sonnet-5-5"

# COMMAND ----------

FQ = f"`{CATALOG}`.`{SCHEMA}`"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {FQ}")
spark.sql(f"CREATE TABLE IF NOT EXISTS {FQ}.lrc_settings (key STRING, value STRING, updated_at TIMESTAMP) "
          "COMMENT 'Ids created by the tutorial notebooks (Genie space, pipeline, dashboard), so later steps can find them.'")


def save_setting(key, value):
    spark.sql(f"""MERGE INTO {FQ}.lrc_settings t USING (SELECT '{key}' AS key, '{value}' AS value) s ON t.key = s.key
                  WHEN MATCHED THEN UPDATE SET value = s.value, updated_at = current_timestamp()
                  WHEN NOT MATCHED THEN INSERT (key, value, updated_at) VALUES (s.key, s.value, current_timestamp())""")


def get_setting(key, default=""):
    row = spark.sql(f"SELECT value FROM {FQ}.lrc_settings WHERE key = '{key}'").first()
    return row[0] if row else default


def warehouse_id():
    if WAREHOUSE_ID:
        return WAREHOUSE_ID
    from databricks.sdk import WorkspaceClient
    whs = list(WorkspaceClient().warehouses.list())
    pick = [x for x in whs if x.enable_serverless_compute] or whs
    if not pick:
        raise ValueError("No SQL warehouse found: set WAREHOUSE_ID in 00_config")
    return pick[0].id


def repo_root():
    """Workspace path of this Git folder (the parent of notebooks/)."""
    nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
    root = nb.split("/notebooks/")[0]
    return root if root.startswith("/Workspace") else "/Workspace" + root


# names used inside the step notebooks
INSTANCE = LAKEBASE_INSTANCE
LAKEBASE_DB = DB = LAKEBASE_DATABASE
APP = APP_NAME
SCOPE = SECRET_SCOPE
JUDGE = JUDGE_ENDPOINT
SPACE_ID = get_setting("genie_space_id")
print(f"Target {CATALOG}.{SCHEMA} · Lakebase {LAKEBASE_INSTANCE}/{LAKEBASE_DATABASE} · Genie space {SPACE_ID or '(not created yet)'}")
