# Databricks notebook source
# MAGIC %md
# MAGIC # 08 · Lakebase: snapshot operational data back to Delta
# MAGIC
# MAGIC Copies the operational tables from Lakebase into Unity Catalog Delta tables, so that analytics, the Lakeflow
# MAGIC pipeline and the Genie Agent see what teams did today:
# MAGIC
# MAGIC | Lakebase | → Delta | Used by |
# MAGIC |---|---|---|
# MAGIC | `ops.lr_actions` | `lr_action_status` | Genie ("what is still open for Reinsurance?"), dashboard |
# MAGIC | `pricing.quotes` | `bronze_pricing_quotes` | Lakeflow `gold_rate_adequacy` |
# MAGIC | `pricing.rate_actions` | `bronze_rate_actions` | Lakeflow `gold_rate_adequacy`, Genie |

# COMMAND ----------

# MAGIC %pip install -q "databricks-sdk>=0.65" "psycopg[binary]>=3.2"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ./00_config

# COMMAND ----------

FQ = f"`{CATALOG}`.`{SCHEMA}`"

# COMMAND ----------

# MAGIC %run ./_lakebase_conn

# COMMAND ----------

import pandas as pd

inst = ensure_instance(INSTANCE)
COPIES = {
    "lr_action_status": ("SELECT * FROM ops.lr_actions", "Team status of loss-ratio actions, snapshotted from the Lakebase operational store (ops.lr_actions)."),
    "bronze_pricing_quotes": ("SELECT quote_id, created_at, line_of_business, region, broker, technical_premium::float8 AS technical_premium, "
                              "quoted_premium::float8 AS quoted_premium, rate_change_pct::float8 AS rate_change_pct, status, underwriter, referral_reason FROM pricing.quotes",
                              "Pricing quotes snapshotted from the Lakebase pricing system (pricing.quotes)."),
    "bronze_rate_actions": ("SELECT rate_action_id, source_action_id, line_of_business, region, rate_change_pct::float8 AS rate_change_pct, reason, "
                            "effective_date, status, proposed_by, decided_by, decided_at FROM pricing.rate_actions",
                            "Rate actions (proposed by the coworker, decided by the pricing desk) snapshotted from Lakebase (pricing.rate_actions)."),
}
with connect(inst, DB) as c:
    for table, (sql, comment) in COPIES.items():
        cur = c.execute(sql)
        df = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
        for col in df.columns:
            if str(df[col].dtype).startswith("datetime64[ns,"):
                df[col] = df[col].dt.tz_convert("UTC").dt.tz_localize(None)
        sdf = spark.createDataFrame(df) if len(df) else spark.sql(f"SELECT * FROM {FQ}.{table} LIMIT 0") if spark.catalog.tableExists(f"{CATALOG}.{SCHEMA}.{table}") else None
        if sdf is None:
            print(f"{table}: source empty, skipped"); continue
        sdf.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{FQ}.{table}")
        spark.sql(f"COMMENT ON TABLE {FQ}.{table} IS '{comment}'")
        print(f"{table}: {len(df):,} rows")

display(spark.sql(f"SELECT team, status, count(*) actions FROM {FQ}.lr_action_status GROUP BY ALL ORDER BY team, status"))

# COMMAND ----------

# Re-apply the app grants (covers the synced table if it came online after Lakebase 02)
grant_app(inst, DB, APP, SCHEMA)
