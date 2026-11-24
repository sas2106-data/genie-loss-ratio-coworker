"""Loss Ratio Action Desk: a Databricks App on Lakebase.

Team leads open it from the morning brief, see which segments are RED, and acknowledge, take or close their actions.
Every change is a Postgres transaction in Lakebase (ops.lr_actions, pricing.rate_actions); a job snapshots it back to
Delta so the Genie Agent can answer "what is still open for Reinsurance?".
"""
import os
import uuid

import pandas as pd
import psycopg
import streamlit as st
from databricks.sdk import WorkspaceClient

st.set_page_config(page_title="Loss Ratio Action Desk", page_icon="🛡️", layout="wide")
w = WorkspaceClient()
INSTANCE = os.environ.get("LAKEBASE_INSTANCE", "lrc-lakebase")
SCHEMA = os.environ.get("LRC_SCHEMA", "loss_ratio_coworker")
TEAMS = ["All", "Claims", "Underwriting", "Pricing", "Reinsurance", "Reserving", "Finance"]


def conn():
    """Lakebase connection as the app's service principal, with a fresh OAuth token (PG* env vars come from the app's database resource)."""
    token = w.database.generate_database_credential(request_id=str(uuid.uuid4()), instance_names=[INSTANCE]).token
    return psycopg.connect(host=os.environ["PGHOST"], port=os.environ.get("PGPORT", "5432"), dbname=os.environ["PGDATABASE"],
                           user=os.environ.get("PGUSER") or w.config.client_id, password=token, sslmode="require")


def query(sql, args=None):
    with conn() as c:
        cur = c.execute(sql, args or ())
        return pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])


def user():
    return st.context.headers.get("X-Forwarded-Email") or st.context.headers.get("X-Forwarded-Preferred-Username") or "unknown"


st.title("🛡️ Loss Ratio Action Desk")
st.caption("Operational view on **Lakebase**: today's watchlist (synced from Delta), the actions the coworker assigned, "
           "and the rate actions it proposed. Updates are written to Postgres and flow back to the lakehouse. Synthetic data.")

try:
    watch = query(f'SELECT * FROM "{SCHEMA}".lr_watchlist_serving ORDER BY gap_7d_pts DESC')
except psycopg.Error as e:
    st.warning(f"Watchlist not available yet ({e.__class__.__name__}); run notebooks 06 and 07 to sync it.")
    watch = pd.DataFrame(columns=["line_of_business", "region", "status", "gap_7d_pts"])
acts = query("SELECT * FROM ops.lr_actions ORDER BY as_of_date DESC, priority, team")
rates = query("SELECT * FROM pricing.rate_actions ORDER BY status, rate_change_pct DESC")

c1, c2, c3, c4 = st.columns(4)
c1.metric("RED segments", int((watch.status == "RED").sum()) if len(watch) else 0)
c2.metric("AMBER segments", int((watch.status == "AMBER").sum()) if len(watch) else 0)
c3.metric("Open actions", int((acts.status != "DONE").sum()) if len(acts) else 0)
c4.metric("Rate actions to decide", int((rates.status == "PROPOSED").sum()) if len(rates) else 0)

tab1, tab2, tab3 = st.tabs(["📋 My team's actions", "🚦 Today's watchlist", "💶 Pricing: rate actions"])

with tab1:
    team = st.selectbox("Team", TEAMS, index=0)
    view = acts if team == "All" else acts[acts.team == team]
    st.dataframe(view[["team", "priority", "status", "owner", "note", "line_of_business", "region", "alert_status",
                       "primary_driver", "action", "due_within", "action_id", "updated_at", "updated_by"]],
                 use_container_width=True, hide_index=True)
    if len(view):
        with st.form("update_action"):
            st.subheader("Update an action")
            aid = st.selectbox("Action", view.action_id.tolist(),
                               format_func=lambda a: f"{a} · {view.set_index('action_id').loc[a, 'action'][:80]}")
            col1, col2 = st.columns(2)
            status = col1.selectbox("Status", ["ACKNOWLEDGED", "IN_PROGRESS", "DONE"])
            owner = col2.text_input("Owner", placeholder="e.g. claims.lead.dach")
            note = st.text_area("Note", placeholder="e.g. adjusters deployed to Munich, 40 claims triaged")
            if st.form_submit_button("Save to Lakebase"):
                with conn() as c:
                    c.execute("UPDATE ops.lr_actions SET status=%s, owner=%s, note=%s, updated_at=now(), updated_by=%s WHERE action_id=%s",
                              (status, owner or user(), note, user(), aid))
                    c.commit()
                st.success(f"{aid} → {status} (saved in Lakebase)")
                st.rerun()

with tab2:
    st.dataframe(watch, use_container_width=True, hide_index=True)
    st.caption("Served from the Lakebase synced table `lr_watchlist_serving` (source: Delta `lr_watchlist_snapshot`).")

with tab3:
    st.dataframe(rates, use_container_width=True, hide_index=True)
    pend = rates[rates.status == "PROPOSED"] if len(rates) else rates
    if len(pend):
        with st.form("decide_rate"):
            rid = st.selectbox("Proposed rate action", pend.rate_action_id.tolist(),
                               format_func=lambda r: f"{r} · {pend.set_index('rate_action_id').loc[r, 'line_of_business']} "
                                                     f"{pend.set_index('rate_action_id').loc[r, 'region']} "
                                                     f"+{pend.set_index('rate_action_id').loc[r, 'rate_change_pct']}%")
            decision = st.radio("Decision", ["APPROVED", "REJECTED"], horizontal=True)
            if st.form_submit_button("Record decision"):
                with conn() as c:
                    c.execute("UPDATE pricing.rate_actions SET status=%s, decided_by=%s, decided_at=now() WHERE rate_action_id=%s",
                              (decision, user(), rid))
                    c.commit()
                st.success(f"{rid} {decision}")
                st.rerun()
