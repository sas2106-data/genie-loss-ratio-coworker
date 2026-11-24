# Databricks notebook source
# MAGIC %md
# MAGIC # 13 · Refresh the Genie Agent with the Lakebase tables
# MAGIC
# MAGIC Step 06 created the agent before Lakebase existed. Running it again adds `lr_action_status` (team status from the
# MAGIC Action Desk) and `gold_rate_adequacy`, with their sample questions. Then try these in the agent or in Genie One:
# MAGIC
# MAGIC - *Which actions are still open for Reinsurance and who owns them?*
# MAGIC - *Where is the loss ratio above target with no rate increase?*
# MAGIC - *Why did DACH Property loss ratio jump this week?*

# COMMAND ----------

# MAGIC %run ./06_genie_agent
