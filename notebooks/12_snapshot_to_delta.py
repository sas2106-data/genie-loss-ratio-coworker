# Databricks notebook source
# MAGIC %md
# MAGIC # 12 · Lakebase: snapshot what teams did back to Delta, and rate adequacy
# MAGIC
# MAGIC Copies the operational tables from Lakebase into Unity Catalog Delta tables, so that analytics, the Lakeflow
# MAGIC pipeline and the Genie Agent see what teams did today:
# MAGIC
# MAGIC | Lakebase | → Delta | Used by |
# MAGIC |---|---|---|
# MAGIC | `ops.lr_actions` | `lr_action_status` | Genie ("what is still open for Reinsurance?"), dashboard |
# MAGIC | `pricing.quotes` | `bronze_pricing_quotes` | `gold_rate_adequacy` |
# MAGIC | `pricing.rate_actions` | `bronze_rate_actions` | `gold_rate_adequacy`, Genie |
# MAGIC
# MAGIC Then `gold_rate_adequacy` joins the pricing transactions with the governed 30-day loss ratio: where is the
# MAGIC loss ratio above target with no rate increase? Re-run this notebook after teams update actions in the app.

# COMMAND ----------

# MAGIC %pip install -q "databricks-sdk>=0.65" "psycopg[binary]>=3.2"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ./00_setup

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

# Re-apply the app grants (covers the synced table if it came online after step 10)
grant_app(inst, DB, APP, SCHEMA)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Rate adequacy: indicated vs achieved rate change

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE VIEW {FQ}.gold_rate_adequacy
COMMENT 'Rate adequacy per line of business × region over the last 30 days. Indicated rate change = 30-day loss ratio ÷ target − 1 (loss-ratio method); compared with the rate change actually achieved on quotes in the Lakebase pricing system and with rate actions the coworker proposed.'
AS
WITH q AS (
  SELECT line_of_business, region, COUNT(*) AS quotes,
         AVG(CASE WHEN status = 'BOUND' THEN 1.0 ELSE 0.0 END) AS bind_ratio,
         AVG(CASE WHEN status = 'REFERRED' THEN 1.0 ELSE 0.0 END) AS referral_ratio,
         AVG(rate_change_pct) AS avg_rate_change_pct,
         AVG(quoted_premium / NULLIF(technical_premium, 0)) AS price_to_technical
  FROM {FQ}.bronze_pricing_quotes
  WHERE CAST(created_at AS DATE) > date_sub(current_date(), 30) GROUP BY ALL
),
ra AS (
  SELECT line_of_business, region, COUNT(*) AS proposed_rate_actions, MAX(rate_change_pct) AS max_proposed_rate_change_pct
  FROM {FQ}.bronze_rate_actions WHERE status = 'PROPOSED' GROUP BY ALL
),
lr AS (
  SELECT line_of_business, region, SUM(incurred_loss) / NULLIF(SUM(earned_premium), 0) AS loss_ratio_30d
  FROM {FQ}.gold_daily_loss_run WHERE as_of_date > date_sub(current_date(), 30) GROUP BY ALL
),
j AS (
  SELECT lr.line_of_business, lr.region,
         ROUND(lr.loss_ratio_30d, 4) AS loss_ratio_30d, t.target_loss_ratio,
         ROUND((lr.loss_ratio_30d - t.target_loss_ratio) * 100, 1) AS lr_gap_pts,
         ROUND((lr.loss_ratio_30d / t.target_loss_ratio - 1) * 100, 1) AS indicated_rate_change_pct,
         q.quotes, ROUND(q.bind_ratio, 3) AS bind_ratio, ROUND(q.referral_ratio, 3) AS referral_ratio,
         ROUND(q.avg_rate_change_pct, 1) AS achieved_rate_change_pct, ROUND(q.price_to_technical, 3) AS price_to_technical,
         COALESCE(ra.proposed_rate_actions, 0) AS proposed_rate_actions, ra.max_proposed_rate_change_pct
  FROM lr
  JOIN {FQ}.lr_targets t USING (line_of_business)
  LEFT JOIN q USING (line_of_business, region)
  LEFT JOIN ra USING (line_of_business, region)
)
SELECT *,
       ROUND(indicated_rate_change_pct - COALESCE(achieved_rate_change_pct, 0), 1) AS rate_shortfall_pts,
       CASE WHEN indicated_rate_change_pct > COALESCE(achieved_rate_change_pct, 0) + 2 AND proposed_rate_actions > 0
              THEN 'Rate action proposed: awaiting pricing decision'
            WHEN indicated_rate_change_pct > COALESCE(achieved_rate_change_pct, 0) + 2
              THEN 'Rate inadequate: achieved rate change below indicated, no rate action'
            WHEN lr_gap_pts > 0 THEN 'Monitor: above target, achieved rate change covers the gap'
            ELSE 'Adequate' END AS adequacy_status
FROM j
""")
display(spark.sql(f"SELECT line_of_business, region, loss_ratio_30d, target_loss_ratio, indicated_rate_change_pct, achieved_rate_change_pct, adequacy_status FROM {FQ}.gold_rate_adequacy ORDER BY rate_shortfall_pts DESC"))
