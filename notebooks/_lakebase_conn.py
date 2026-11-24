# Databricks notebook source
# MAGIC %md
# MAGIC # Lakebase connection helper (`%run ./_lakebase_conn`)
# MAGIC Gets or creates the Lakebase Postgres instance, then opens a `psycopg` connection with a short-lived OAuth
# MAGIC token for the current identity (no passwords stored anywhere).

# COMMAND ----------

import time, uuid
import psycopg
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import DatabaseInstance

w = WorkspaceClient()
ME = w.current_user.me().user_name


def ensure_instance(name: str, capacity: str = "CU_1") -> DatabaseInstance:
    """Return the Lakebase instance, creating it (and waiting until AVAILABLE) if it does not exist."""
    try:
        inst = w.database.get_database_instance(name)
    except Exception:
        print(f"Creating Lakebase instance {name} ({capacity}) …")
        w.database.create_database_instance(DatabaseInstance(name=name, capacity=capacity))
        inst = w.database.get_database_instance(name)
    for _ in range(90):
        state = str(inst.state).split(".")[-1]
        if state == "AVAILABLE":
            return inst
        time.sleep(20)
        inst = w.database.get_database_instance(name)
    raise TimeoutError(f"Lakebase instance {name} not AVAILABLE (state {inst.state})")


def connect(instance: DatabaseInstance, dbname: str = "databricks_postgres", autocommit: bool = False):
    """psycopg connection to Lakebase using a database credential (OAuth token) for the current identity."""
    cred = w.database.generate_database_credential(request_id=str(uuid.uuid4()), instance_names=[instance.name])
    return psycopg.connect(host=instance.read_write_dns, port=5432, dbname=dbname, user=ME,
                           password=cred.token, sslmode="require", autocommit=autocommit)


def ensure_database(instance: DatabaseInstance, dbname: str) -> None:
    with connect(instance, autocommit=True) as c:
        if not c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)).fetchone():
            c.execute(f'CREATE DATABASE "{dbname}"')
            print(f"created Postgres database {dbname}")


def grant_app(instance: DatabaseInstance, dbname: str, app_name: str, synced_schema: str) -> None:
    """Grant the Action Desk app's service principal what it needs in Postgres. Safe to re-run; skips if the app is not deployed."""
    try:
        sp = w.apps.get(app_name).service_principal_client_id
    except Exception as e:  # noqa: BLE001
        print(f"app grant skipped ({app_name} not deployed): {str(e)[:120]}")
        return
    with connect(instance, dbname, autocommit=True) as c:
        has_synced = c.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (synced_schema,)).fetchone()
        stmts = ['GRANT USAGE ON SCHEMA ops, pricing TO "{sp}"',
                 'GRANT SELECT, UPDATE ON ops.lr_actions TO "{sp}"',
                 'GRANT SELECT, UPDATE ON pricing.rate_actions TO "{sp}"',
                 'GRANT SELECT ON pricing.quotes TO "{sp}"']
        if has_synced:
            stmts += ['GRANT USAGE ON SCHEMA "{sch}" TO "{sp}"', 'GRANT SELECT ON ALL TABLES IN SCHEMA "{sch}" TO "{sp}"']
        for stmt in stmts:
            c.execute(stmt.format(sp=sp, sch=synced_schema))
    print(f"granted app {app_name} ({sp}) access to ops, pricing" + (f" and synced schema {synced_schema}" if has_synced else " (synced schema not there yet)"))
