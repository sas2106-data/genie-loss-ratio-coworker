# Databricks notebook source
# MAGIC %md
# MAGIC # 14 · Refresh the Genie Agent with the pipeline, data-quality and Lakebase tables
# MAGIC
# MAGIC Step 04 created the agent before the pipeline and the Lakebase snapshots existed. Running it again adds
# MAGIC `dq_daily_scorecard`, `dq_claims_issues`, `lr_action_status`, `gold_rate_adequacy` and `gold_daily_loss_run_lf`,
# MAGIC with their sample questions. Then try these in the agent:
# MAGIC
# MAGIC - *Why did DACH Property loss ratio jump this week?*
# MAGIC - *Which data-quality checks failed today and why?*
# MAGIC - *Which actions are still open for Reinsurance and who owns them?*
# MAGIC - *Where is the loss ratio above target with no rate increase?*

# COMMAND ----------

# MAGIC %run ./04_genie_agent
