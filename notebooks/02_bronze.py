# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Pipeline, bronze: load the raw files with Auto Loader
# MAGIC
# MAGIC Creates the Lakeflow Spark Declarative Pipeline with one source file, `pipeline/01_bronze.sql`, and runs it.
# MAGIC Open that file next to this notebook: two **streaming tables** read the raw volume with `read_files` as a stream
# MAGIC (Auto Loader), so each file is ingested exactly once and new files are picked up on the next run.
# MAGIC
# MAGIC | Table | From |
# MAGIC |---|---|
# MAGIC | `bronze_fnol` | `raw/claims_fnol/**` JSON, as landed, plus `source_file` and `ingested_at` |
# MAGIC | `bronze_premium` | `raw/premium_bordereaux/**` CSV, as landed |

# COMMAND ----------

# MAGIC %run ./00_setup

# COMMAND ----------

# MAGIC %run ./_pipeline

# COMMAND ----------

run_pipeline(["bronze"])

# COMMAND ----------

display(spark.sql(f"""
  SELECT 'bronze_fnol' AS table_name, COUNT(*) AS records, COUNT(DISTINCT source_file) AS files FROM {FQ}.bronze_fnol
  UNION ALL
  SELECT 'bronze_premium', COUNT(*), COUNT(DISTINCT source_file) FROM {FQ}.bronze_premium"""))
display(spark.sql(f"SELECT * FROM {FQ}.bronze_fnol LIMIT 5"))
