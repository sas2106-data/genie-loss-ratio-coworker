# Databricks notebook source
# MAGIC %md
# MAGIC # Lakebase 01 · Operational store for actions, team status and pricing transactions
# MAGIC
# MAGIC **Lakebase** (managed, serverless Postgres) is the coworker's **low-latency operational layer**. Delta stays the
# MAGIC analytical system of record; Lakebase holds the rows that people and apps *change* during the day.
# MAGIC
# MAGIC | Postgres table | Written by | Read by |
# MAGIC |---|---|---|
# MAGIC | `ops.lr_actions` | the daily job publishes new actions; team leads update **status, owner, note** in the Action Desk app | Action Desk app; snapshotted back to Delta for Genie |
# MAGIC | `pricing.quotes` | the pricing desk (simulated transactional quoting) | Lakeflow `gold_rate_adequacy` (via Delta snapshot) |
# MAGIC | `pricing.rate_actions` | the coworker proposes rate changes for Pricing actions; the pricing desk approves/rejects | Action Desk app, `gold_rate_adequacy` |
# MAGIC | `<schema>.lr_watchlist_serving` | **synced table** from Delta `lr_watchlist_snapshot` (created in Lakebase 02) | Action Desk app (millisecond reads) |
# MAGIC
# MAGIC This notebook is idempotent: it creates the instance, database, schemas and tables if missing, and seeds 120
# MAGIC days of synthetic quotes once.

# COMMAND ----------

# MAGIC %pip install -q "databricks-sdk>=0.65" "psycopg[binary]>=3.2"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.text("catalog", "")
dbutils.widgets.text("schema", "loss_ratio_coworker")
dbutils.widgets.text("lakebase_instance", "lrc-lakebase")
dbutils.widgets.text("lakebase_database", "lrc_ops")
CATALOG = dbutils.widgets.get("catalog") or spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = dbutils.widgets.get("schema")
INSTANCE = dbutils.widgets.get("lakebase_instance")
DB = dbutils.widgets.get("lakebase_database")

# COMMAND ----------

# MAGIC %run ./_lakebase_conn

# COMMAND ----------

inst = ensure_instance(INSTANCE)
ensure_database(inst, DB)
print(f"Lakebase instance {inst.name} · host {inst.read_write_dns} · database {DB}")

DDL = """
CREATE SCHEMA IF NOT EXISTS ops;
CREATE SCHEMA IF NOT EXISTS pricing;

CREATE TABLE IF NOT EXISTS ops.lr_actions (
  action_id      TEXT PRIMARY KEY,           -- alert_id + team, stable across re-publishes
  alert_id       TEXT NOT NULL,
  as_of_date     DATE NOT NULL,
  line_of_business TEXT NOT NULL,
  region         TEXT NOT NULL,
  alert_status   TEXT NOT NULL,              -- RED / AMBER
  primary_driver TEXT,
  team           TEXT NOT NULL,
  priority       TEXT NOT NULL,              -- P1 / P2
  action         TEXT NOT NULL,
  due_within     TEXT,
  status         TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS','DONE')),
  owner          TEXT,
  note           TEXT,
  published_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_by     TEXT
);
CREATE INDEX IF NOT EXISTS lr_actions_team_status ON ops.lr_actions (team, status);

CREATE TABLE IF NOT EXISTS pricing.quotes (
  quote_id          TEXT PRIMARY KEY,
  created_at        TIMESTAMPTZ NOT NULL,
  line_of_business  TEXT NOT NULL,
  region            TEXT NOT NULL,
  broker            TEXT NOT NULL,
  technical_premium NUMERIC(14,2) NOT NULL,
  quoted_premium    NUMERIC(14,2) NOT NULL,
  rate_change_pct   NUMERIC(6,2) NOT NULL,     -- vs expiring
  status            TEXT NOT NULL CHECK (status IN ('QUOTED','BOUND','DECLINED','REFERRED')),
  underwriter       TEXT NOT NULL,
  referral_reason   TEXT
);
CREATE INDEX IF NOT EXISTS quotes_segment ON pricing.quotes (line_of_business, region, created_at);

CREATE TABLE IF NOT EXISTS pricing.rate_actions (
  rate_action_id    TEXT PRIMARY KEY,
  source_action_id  TEXT UNIQUE,              -- ops.lr_actions.action_id that triggered it (idempotent)
  line_of_business  TEXT NOT NULL,
  region            TEXT NOT NULL,
  rate_change_pct   NUMERIC(6,2) NOT NULL,
  reason            TEXT NOT NULL,
  effective_date    DATE NOT NULL,
  status            TEXT NOT NULL DEFAULT 'PROPOSED' CHECK (status IN ('PROPOSED','APPROVED','REJECTED')),
  proposed_by       TEXT NOT NULL,
  decided_by        TEXT,
  decided_at        TIMESTAMPTZ
);
"""
with connect(inst, DB) as c:
    c.execute(DDL)
    c.commit()
print("schemas ops, pricing and tables ready")

# COMMAND ----------

# MAGIC %md ## Seed 120 days of synthetic quotes (once)

# COMMAND ----------

import numpy as np
from datetime import datetime, timedelta, timezone

LOBS = {"Property": (12000, 0.03), "Motor": (6000, 0.04), "Liability": (9000, 0.02), "Marine": (15000, 0.025)}
REGIONS = ["UK & Ireland", "France", "DACH", "Southern Europe", "Benelux"]
BROKERS = ["Broker A", "Broker B", "Broker C", "Broker D", "Direct"]
UWS = ["uw.anna", "uw.marc", "uw.lena", "uw.paolo", "uw.sofie"]

with connect(inst, DB) as c:
    n = c.execute("SELECT count(*) FROM pricing.quotes").fetchone()[0]
    if n == 0:
        rng = np.random.default_rng(11)
        now = datetime.now(timezone.utc)
        rows = []
        for i in range(24000):
            lob = rng.choice(list(LOBS)); region = rng.choice(REGIONS)
            base, rate = LOBS[lob]
            tech = float(np.round(np.exp(rng.normal(np.log(base), 0.6)), 2))
            rc = float(np.round(rng.normal(rate * 100, 2.5), 2))
            quoted = round(tech * (1 + rng.normal(-0.01, 0.06)), 2)
            status = rng.choice(["QUOTED", "BOUND", "DECLINED", "REFERRED"], p=[0.35, 0.42, 0.18, 0.05])
            rows.append((f"Q-{i:07d}", now - timedelta(days=float(rng.uniform(0, 120))), lob, region, rng.choice(BROKERS),
                         tech, quoted, rc, status, rng.choice(UWS), None))
        with c.cursor() as cur:
            cur.executemany("INSERT INTO pricing.quotes VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", rows)
        c.commit()
        n = len(rows)
        print(f"seeded {n:,} quotes")
    else:
        print(f"pricing.quotes already has {n:,} rows")
    for t in ["ops.lr_actions", "pricing.quotes", "pricing.rate_actions"]:
        print(t, c.execute(f"SELECT count(*) FROM {t}").fetchone()[0])
