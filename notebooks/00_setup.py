# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Setup: settings, catalog, schema and raw volume
# MAGIC
# MAGIC Set the values in the next cell **once**, then run this notebook. It creates the catalog (if it does not exist and
# MAGIC you are allowed to), the schema and the `raw` volume. Every other notebook starts with `%run ./00_setup`, so they
# MAGIC all use the same settings.
# MAGIC
# MAGIC | Setting | What it is |
# MAGIC |---|---|
# MAGIC | `CATALOG`, `SCHEMA` | where everything is created: tables, views, the raw volume, the pipeline output |
# MAGIC | `WAREHOUSE_ID` | serverless SQL warehouse for the Genie Agent and the dashboard; blank = the first serverless warehouse |
# MAGIC | `LLM_ENDPOINT` | model used by `ai_query` in the silver data-quality step |
# MAGIC | `MAX_AI_CLAIMS`, `AI_LOOKBACK_DAYS` | the Gen AI checks read at most about 2,000 of the most recent claims (keeps step 03 quick and cheap) |
# MAGIC | `FULL_REFRESH` | set to `True` once if you re-run step 01, so the pipeline re-reads the new files |
# MAGIC | `LAKEBASE_*`, `APP_NAME` | Lakebase instance, database and the Action Desk app. If you change them, change `app/action_desk/app.yaml` too |
# MAGIC | `JUDGE_ENDPOINT` | used only by the optional notebooks |

# COMMAND ----------

CATALOG = "main"                          # <-- change to your catalog
SCHEMA = "loss_ratio_coworker"
WAREHOUSE_ID = ""                         # blank = first serverless SQL warehouse found

LLM_ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"
MAX_AI_CLAIMS = 2000                      # Gen AI checks run on at most this many of the newest claims
AI_LOOKBACK_DAYS = 14                     # ... reported in the last N days
FULL_REFRESH = False                      # True after re-running step 01 (used by step 02)

DAILY_DROP_DAYS = 30                      # step 01 lands the last 30 days as daily files, older history as monthly files
FILES_PER_DAY = 2

LAKEBASE_INSTANCE = "lrc-lakebase"
LAKEBASE_DATABASE = "lrc_ops"
APP_NAME = "lrc-action-desk"
JUDGE_ENDPOINT = "databricks-gpt-oss-120b"      # optional notebooks: a different model family from LLM_ENDPOINT

# COMMAND ----------

# Catalog: use it if it exists, otherwise try to create it (needs the CREATE CATALOG privilege)
try:
    spark.sql(f"DESCRIBE CATALOG `{CATALOG}`")
except Exception:
    try:
        spark.sql(f"CREATE CATALOG IF NOT EXISTS `{CATALOG}`")
        print(f"created catalog {CATALOG}")
    except Exception as e:
        raise RuntimeError(f"Catalog {CATALOG} does not exist and could not be created: ask an admin, "
                           f"or set CATALOG to a catalog you can use. ({str(e).splitlines()[0][:200]})")

FQ = f"`{CATALOG}`.`{SCHEMA}`"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {FQ} COMMENT 'Genie Loss Ratio Coworker tutorial (synthetic data)'")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {FQ}.raw COMMENT 'Raw landing zone: FNOL claims (JSON) and premium bordereaux (CSV)'")
RAW = f"/Volumes/{CATALOG}/{SCHEMA}/raw"
spark.sql(f"CREATE TABLE IF NOT EXISTS {FQ}.lrc_settings (key STRING, value STRING, updated_at TIMESTAMP) "
          "COMMENT 'Ids created by the tutorial notebooks (pipeline, Genie space, dashboard), so later steps can find them.'")


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
        raise ValueError("No SQL warehouse found: set WAREHOUSE_ID in 00_setup")
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
JUDGE = JUDGE_ENDPOINT
SPACE_ID = get_setting("genie_space_id")
print(f"Ready: {CATALOG}.{SCHEMA} · raw volume {RAW} · Genie space {SPACE_ID or '(created in step 06)'}")
