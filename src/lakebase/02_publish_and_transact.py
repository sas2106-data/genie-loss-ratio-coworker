# Databricks notebook source
# MAGIC %md
# MAGIC # Lakebase 02 · Publish actions, record pricing transactions, sync the watchlist
# MAGIC
# MAGIC Runs every morning after the daily watch:
# MAGIC
# MAGIC 1. **Publish actions** from Delta `lr_action_recommendations` into Lakebase `ops.lr_actions`.
# MAGIC    `INSERT … ON CONFLICT DO NOTHING`, so a team's status, owner and notes are never overwritten by a re-run.
# MAGIC 2. **Pricing transactions**: today's quotes from the pricing desk (simulated), with a **referral** when the
# MAGIC    segment is RED, and one **PROPOSED rate action** per Pricing action from the coworker (idempotent on
# MAGIC    `source_action_id`). All in a single Postgres transaction.
# MAGIC 3. **Synced table**: refresh Delta `lr_watchlist_snapshot` and sync it into Lakebase as
# MAGIC    `lr_watchlist_serving`, so the Action Desk app reads today's RAG status in milliseconds.
# MAGIC 4. Grant the Action Desk app's service principal access to the operational tables (if the app exists).

# COMMAND ----------

# MAGIC %pip install -q "databricks-sdk>=0.65" "psycopg[binary]>=3.2"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.text("catalog", "")
dbutils.widgets.text("schema", "loss_ratio_coworker")
dbutils.widgets.text("lakebase_instance", "lrc-lakebase")
dbutils.widgets.text("lakebase_database", "lrc_ops")
dbutils.widgets.text("app_name", "lrc-action-desk")
CATALOG = dbutils.widgets.get("catalog") or spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = dbutils.widgets.get("schema")
INSTANCE = dbutils.widgets.get("lakebase_instance")
DB = dbutils.widgets.get("lakebase_database")
APP = dbutils.widgets.get("app_name")
FQ = f"`{CATALOG}`.`{SCHEMA}`"

# COMMAND ----------

# MAGIC %run ./_lakebase_conn

# COMMAND ----------

inst = ensure_instance(INSTANCE)

# Latest alert per segment and its actions (the daily watch appends; take the newest run)
actions = spark.sql(f"""
  WITH latest AS (SELECT MAX(as_of_date) d FROM {FQ}.lr_alerts)
  SELECT a.alert_id, a.as_of_date, a.line_of_business, a.region, a.status AS alert_status, a.primary_driver,
         r.team, r.priority, r.action, r.due_within
  FROM {FQ}.lr_alerts a JOIN {FQ}.lr_action_recommendations r USING (alert_id)
  WHERE a.as_of_date = (SELECT d FROM latest)
""").toPandas()
watch = spark.table(f"{FQ}.v_loss_ratio_watchlist").toPandas()
print(f"{len(actions)} actions for {actions.alert_id.nunique() if len(actions) else 0} alerts; {len(watch)} watchlist segments")

# COMMAND ----------

import time
import numpy as np
from datetime import datetime, timezone

RATE_BY_DRIVER = {"frequency": 7.5, "severity": 5.0, "large loss": 2.5, "catastrophe event": 4.0}
red = {(r.line_of_business, r.region) for r in watch.itertuples() if r.status == "RED"}
rng = np.random.default_rng(int(datetime.now().strftime("%Y%m%d")))

with connect(inst, DB) as c:
    with c.transaction():
        # 1 · actions (keep team updates on conflict)
        pub = 0
        for r in actions.itertuples():
            cur = c.execute("""INSERT INTO ops.lr_actions (action_id, alert_id, as_of_date, line_of_business, region, alert_status,
                                 primary_driver, team, priority, action, due_within)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (action_id) DO NOTHING""",
                            (f"{r.alert_id}:{r.team}", r.alert_id, r.as_of_date, r.line_of_business, r.region, r.alert_status,
                             r.primary_driver, r.team, r.priority, r.action, r.due_within))
            pub += cur.rowcount
        # 2a · today's quotes from the pricing desk; RED segments are referred to a senior underwriter
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        if not c.execute("SELECT 1 FROM pricing.quotes WHERE quote_id LIKE %s LIMIT 1", (f"Q-{day}-%",)).fetchone():
            qrows = []
            for i in range(300):
                lob = str(rng.choice(["Property", "Motor", "Liability", "Marine"]))
                region = str(rng.choice(["UK & Ireland", "France", "DACH", "Southern Europe", "Benelux"]))
                tech = float(np.round(np.exp(rng.normal(9.0, 0.6)), 2))
                referred = (lob, region) in red
                qrows.append((f"Q-{day}-{i:04d}", datetime.now(timezone.utc), lob, region, str(rng.choice(["Broker A", "Broker B", "Broker C", "Direct"])),
                              tech, round(tech * (1 + rng.normal(0.0, 0.05)), 2), round(float(rng.normal(3.0, 2.5)), 2),
                              "REFERRED" if referred else str(rng.choice(["QUOTED", "BOUND", "DECLINED"], p=[0.4, 0.42, 0.18])),
                              "uw.desk", "Segment RED on loss ratio: senior underwriter referral" if referred else None))
            with c.cursor() as cur:
                cur.executemany("INSERT INTO pricing.quotes VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", qrows)
            print(f"recorded {len(qrows)} quotes ({sum(q[8] == 'REFERRED' for q in qrows)} referred)")
        # 2b · coworker → pricing system: one proposed rate action per Pricing action
        props = 0
        for r in actions[actions.team == "Pricing"].itertuples():
            cur = c.execute("""INSERT INTO pricing.rate_actions (rate_action_id, source_action_id, line_of_business, region,
                                 rate_change_pct, reason, effective_date, proposed_by)
                               VALUES (%s,%s,%s,%s,%s,%s,current_date + 30,%s) ON CONFLICT (source_action_id) DO NOTHING""",
                            (f"RA-{r.alert_id}", f"{r.alert_id}:{r.team}", r.line_of_business, r.region,
                             RATE_BY_DRIVER.get(str(r.primary_driver).lower(), 3.0),
                             f"{r.alert_status} on loss ratio, driver {r.primary_driver}: {r.action}", "loss-ratio-coworker"))
            props += cur.rowcount
    print(f"published {pub} new actions · proposed {props} rate actions")
    for t in ["ops.lr_actions", "pricing.quotes", "pricing.rate_actions"]:
        print(t, c.execute(f"SELECT count(*) FROM {t}").fetchone()[0])

# COMMAND ----------

# MAGIC %md ## 3 · Synced table: today's watchlist served from Lakebase

# COMMAND ----------

from databricks.sdk.service.database import SyncedDatabaseTable, SyncedTableSpec, SyncedTableSchedulingPolicy

spark.sql(f"""CREATE OR REPLACE TABLE {FQ}.lr_watchlist_snapshot
  COMMENT 'Snapshot of v_loss_ratio_watchlist for serving from Lakebase (synced table lr_watchlist_serving).'
  AS SELECT line_of_business, region, status, primary_driver, lr_7d, lr_30d, lr_ytd, target_loss_ratio, gap_7d_pts,
            current_timestamp() AS snapshot_at
  FROM {FQ}.v_loss_ratio_watchlist""")
spark.sql(f"ALTER TABLE {FQ}.lr_watchlist_snapshot SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")

SYNCED = f"{CATALOG}.{SCHEMA}.lr_watchlist_serving"
try:
    st = w.database.get_synced_database_table(SYNCED)
    pid = st.data_synchronization_status.pipeline_id if st.data_synchronization_status else None
    if pid:
        w.pipelines.start_update(pid)
    print(f"refreshing synced table {SYNCED} (pipeline {pid})")
except Exception:
    st = w.database.create_synced_database_table(SyncedDatabaseTable(
        name=SYNCED, database_instance_name=INSTANCE, logical_database_name=DB,
        spec=SyncedTableSpec(source_table_full_name=f"{CATALOG}.{SCHEMA}.lr_watchlist_snapshot",
                             primary_key_columns=["line_of_business", "region"],
                             scheduling_policy=SyncedTableSchedulingPolicy.SNAPSHOT)))
    print(f"created synced table {SYNCED} → Lakebase {INSTANCE}/{DB}")

# COMMAND ----------

# MAGIC %md ## 4 · Grant the Action Desk app access (if deployed)

# COMMAND ----------

# The synced table is created asynchronously: wait (up to ~10 min) until it is online, then grant
for _ in range(40):
    state = str(w.database.get_synced_database_table(SYNCED).data_synchronization_status.detailed_state)
    if "ONLINE" in state or "FAILED" in state:
        break
    time.sleep(15)
print(f"synced table state: {state}")
grant_app(inst, DB, APP, SCHEMA)
