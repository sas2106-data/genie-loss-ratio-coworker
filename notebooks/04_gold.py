# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · Pipeline, gold: the daily loss run
# MAGIC
# MAGIC Adds `pipeline/03_gold.sql` and refreshes only the new gold table, so the Gen AI checks in silver don't run again. `gold_daily_loss_run` has one row per day, line of business
# MAGIC and region: incurred loss on the date it was reported and the premium earned that day. It is the single table the
# MAGIC metric views (step 05) build the governed loss ratio on.

# COMMAND ----------

# MAGIC %run ./00_setup

# COMMAND ----------

# MAGIC %run ./_pipeline

# COMMAND ----------

run_pipeline(["bronze", "silver", "gold"], refresh=["gold_daily_loss_run"])   # silver and its Gen AI checks are already up to date

# COMMAND ----------

display(spark.sql(f"""
  SELECT line_of_business, region,
         ROUND(SUM(IF(as_of_date > current_date() - 7,  incurred_loss, 0)) / NULLIF(SUM(IF(as_of_date > current_date() - 7,  earned_premium, 0)), 0), 3) AS lr_7d,
         ROUND(SUM(IF(as_of_date > current_date() - 30, incurred_loss, 0)) / NULLIF(SUM(IF(as_of_date > current_date() - 30, earned_premium, 0)), 0), 3) AS lr_30d,
         SUM(IF(as_of_date > current_date() - 7, claim_count, 0)) AS claims_7d
  FROM {FQ}.gold_daily_loss_run GROUP BY ALL ORDER BY lr_7d DESC"""))
