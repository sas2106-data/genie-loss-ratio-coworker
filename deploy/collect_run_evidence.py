"""Collect readable evidence of the latest end-to-end run into docs/run_evidence/ (Markdown + CSV, no binaries).

What it writes:
  README.md                 index + headline numbers
  01_job_run.md             task graph outcome: state, start, duration per task, run URL
  02_notebook_outputs.md    every notebook task's cells with their real printed/displayed output
  03_lakeflow_pipeline.md   pipeline update, datasets written, expectation pass/fail counts (event log)
  04_query_results.md       the business answers: DQ scorecard, Gen AI issues, rate adequacy, reconciliation…
  05_lakebase.md            Lakebase instance, synced table, operational-table counts and team status
  csv/*.csv                 the same query results as CSV

Usage (same env vars as the other deploy scripts):
  LRC_CATALOG=<catalog> LRC_WAREHOUSE_ID=<id> DATABRICKS_CONFIG_PROFILE=<profile> python deploy/collect_run_evidence.py
"""
from __future__ import annotations

import base64
import csv
import json
import re
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from common import CATALOG, SCHEMA, WAREHOUSE_ID, cli, fq

OUT = Path(__file__).resolve().parents[1] / "docs" / "run_evidence"
JOB_MATCH = "End-to-end daily run"
INSTANCE = "lrc-lakebase"
APP = "lrc-action-desk"
MAX_ROWS = 25


# ---------- helpers ----------
def ts(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if ms else ""


def md_table(cols, rows, limit=MAX_ROWS):
    def cell(v):
        s = "" if v is None else str(v)
        return s.replace("|", "\\|").replace("\n", " ")[:220]
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows[:limit]]
    if len(rows) > limit:
        out.append(f"\n_{len(rows) - limit} more rows in the CSV._")
    return "\n".join(out)


def sql(statement):
    res = cli("api", "post", "/api/2.0/sql/statements/", body={
        "statement": statement, "warehouse_id": WAREHOUSE_ID, "format": "JSON_ARRAY",
        "disposition": "INLINE", "wait_timeout": "50s"})
    while res["status"]["state"] in ("PENDING", "RUNNING"):
        time.sleep(3)
        res = cli("api", "get", f"/api/2.0/sql/statements/{res['statement_id']}")
    if res["status"]["state"] != "SUCCEEDED":
        raise RuntimeError(res["status"].get("error", {}).get("message", res["status"]["state"]))
    cols = [c["name"] for c in res["manifest"]["schema"]["columns"]]
    return cols, res.get("result", {}).get("data_array", []) or []


def notebook_cells(task_run_id):
    """Decode the notebook model embedded in a run export: (code, [outputs]) per cell."""
    exp = cli("jobs", "export-run", str(task_run_id), "--views-to-export", "CODE")
    html = exp["views"][0]["content"]
    m = re.search(r"__DATABRICKS_NOTEBOOK_MODEL = '([^']+)'", html)
    model = json.loads(urllib.parse.unquote(base64.b64decode(m.group(1)).decode()))
    cells = []
    for c in model["commands"]:
        code = c.get("command", "")
        r = c.get("results") or {}
        outs = []
        if r.get("type") == "listResults":
            for item in r.get("data") or []:
                if item.get("type") in ("ansi", "text") and item.get("data"):
                    outs.append(("text", re.sub(r"\x1b\[[0-9;]*m", "", item["data"]).strip()))
        elif r.get("type") == "table":
            cols = [s["name"] for s in r.get("schema", [])]
            outs.append(("table", (cols, r.get("data") or [])))
        elif r.get("type") in ("ansi", "text") and r.get("data"):
            outs.append(("text", re.sub(r"\x1b\[[0-9;]*m", "", str(r["data"])).strip()))
        if r.get("type") == "error" or c.get("errorSummary"):
            outs.append(("text", "ERROR: " + re.sub(r"<[^>]+>", "", str(c.get("errorSummary") or r.get("data")))[:1500]))
        cells.append((code, outs))
    return cells


# ---------- 01 job run ----------
def latest_run():
    jobs = cli("jobs", "list", "--name", "")  # list all, filter locally
    jobs = jobs if isinstance(jobs, list) else jobs.get("jobs", [])
    job = next(j for j in jobs if JOB_MATCH in j["settings"]["name"])
    runs = cli("jobs", "list-runs", "--job-id", str(job["job_id"]), "--limit", "5")
    runs = runs if isinstance(runs, list) else runs.get("runs", [])
    done = [r for r in runs if r["state"].get("life_cycle_state") == "TERMINATED"] or runs
    return job, cli("jobs", "get-run", str(done[0]["run_id"]))


def write_job(job, run):
    rows = []
    for t in sorted(run["tasks"], key=lambda t: t.get("start_time") or 0):
        dur = ((t.get("end_time") or 0) - (t.get("start_time") or 0)) / 1000
        deps = ", ".join(d["task_key"] for d in t.get("depends_on", []))
        kind = "Lakeflow pipeline" if "pipeline_task" in t else "notebook"
        rows.append([t["task_key"], kind, deps, t["state"].get("result_state", t["state"].get("life_cycle_state")),
                     ts(t.get("start_time")), f"{dur / 60:.1f} min"])
    total = ((run.get("end_time") or 0) - (run.get("start_time") or 0)) / 60000
    body = f"""# 01 · Job run: `{job['settings']['name']}`

| | |
|---|---|
| Job id | `{job['job_id']}` |
| Run id | `{run['run_id']}` |
| Result | **{run['state'].get('result_state', run['state'].get('life_cycle_state'))}** |
| Started | {ts(run.get('start_time'))} |
| Wall-clock | {total:.1f} min |
| Run URL | {run.get('run_page_url', '')} |

Defined in [`resources/lrc_jobs.yml`](../../resources/lrc_jobs.yml) (job `lrc_end_to_end`).

{md_table(['Task', 'Type', 'Depends on', 'Result', 'Started', 'Duration'], rows)}
"""
    (OUT / "01_job_run.md").write_text(body)
    return rows


# ---------- 02 notebook outputs ----------
def write_notebooks(run):
    parts = ["# 02 · Notebook outputs (captured from the job run)\n",
             "Each section is one notebook task: the code that ran and the output it printed or displayed. "
             "Markdown cells and setup cells without output are omitted.\n"]
    for t in sorted(run["tasks"], key=lambda t: t.get("start_time") or 0):
        if "notebook_task" not in t:
            continue
        parts.append(f"\n## Task `{t['task_key']}` · `{t['notebook_task']['notebook_path'].split('/files/')[-1]}`\n")
        try:
            cells = notebook_cells(t["run_id"])
        except Exception as e:  # noqa: BLE001
            parts.append(f"_could not export: {e}_\n")
            continue
        for code, outs in cells:
            if not outs or code.lstrip().startswith(("%md", "%pip", "dbutils.library")):
                continue
            first = code.strip().splitlines()[0][:120] if code.strip() else ""
            parts.append(f"\n**Cell** `{first}`\n")
            for kind, val in outs:
                if kind == "text":
                    parts.append("```text\n" + val[:4000] + "\n```")
                else:
                    cols, data = val
                    parts.append(md_table(cols, data, 20))
    (OUT / "02_notebook_outputs.md").write_text("\n".join(parts) + "\n")


# ---------- 03 pipeline ----------
def write_pipeline(run):
    t = next((t for t in run["tasks"] if "pipeline_task" in t), None)
    if not t:
        return []
    pid = t["pipeline_task"]["pipeline_id"]
    p = cli("pipelines", "get", pid)
    latest_update = p.get("latest_updates", [{}])[0]
    uid = latest_update.get("update_id")
    _, fl = sql(f"""SELECT split(origin.flow_name, '[.]')[2], details:flow_progress.metrics.num_output_rows
                    FROM event_log('{pid}') WHERE origin.update_id = '{uid}' AND event_type = 'flow_progress'
                      AND details:flow_progress.status = 'COMPLETED'""")
    flows = {r[0]: r[1] for r in fl}
    _, er = sql(f"""SELECT split(x.dataset, '[.]')[2], x.name, x.passed_records, x.failed_records
                    FROM (SELECT explode(from_json(details:flow_progress.data_quality.expectations,
                          'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) x
                          FROM event_log('{pid}') WHERE origin.update_id = '{uid}' AND event_type = 'flow_progress'
                            AND details:flow_progress.data_quality IS NOT NULL)""")
    exp_rows = [list(r) for r in er]
    exp_rows.sort()
    lib = "src/pipeline/lrc_ingest_pipeline.sql"
    body = f"""# 03 · Lakeflow Spark Declarative Pipeline: `{p.get('name')}`

| | |
|---|---|
| Pipeline id | `{pid}` |
| Source | [`{lib}`](../../{lib}) |
| Compute | serverless |
| Latest update | `{uid}` · **{latest_update.get('state')}** · {latest_update.get('creation_time', '')} |

## Datasets written in this update

{md_table(['Dataset', 'Rows written'], sorted([[k, v] for k, v in flows.items()]), 50)}

## Expectations (data-quality rules) from the pipeline event log

{md_table(['Dataset', 'Expectation', 'Passed', 'Failed'], exp_rows, 50) if exp_rows else '_No expectation metrics in the event log for this update._'}
"""
    (OUT / "03_lakeflow_pipeline.md").write_text(body)
    return exp_rows


# ---------- 04 queries ----------
QUERIES = [
    ("dq_scorecard_latest", "Data-quality scorecard, latest report date (rule-based + Gen AI checks)",
     f"""SELECT report_date, check_name, check_type, severity, issues, records_checked, pass_rate
         FROM {fq('dq_daily_scorecard')} WHERE report_date = (SELECT MAX(report_date) FROM {fq('dq_daily_scorecard')})
         ORDER BY issues DESC"""),
    ("dq_issues_by_check", "Issues found over the lookback window, by check",
     f"SELECT check_name, check_type, severity, count(*) issues FROM {fq('dq_claims_issues')} GROUP BY ALL ORDER BY issues DESC"),
    ("dq_genai_examples", "Gen AI findings with the ai_query explanation (descriptions are ai_mask'ed)",
     f"""SELECT claim_id, report_date, check_name, cause_of_loss, ai_peril, loss_description_masked, ai_explanation FROM {fq('dq_claims_issues')}
         WHERE check_type = 'Gen AI' ORDER BY report_date DESC, check_name LIMIT 12"""),
    ("genai_accuracy", "Gen AI check accuracy against seeded defects (src/genai/04_evaluate_genai_dq.py)",
     f"""SELECT check_name, genai_function, claims_checked, seeded_defects, flagged, true_positives, false_positives,
                false_negatives, precision, recall, f1 FROM {fq('dq_genai_eval')}
         WHERE evaluated_at = (SELECT MAX(evaluated_at) FROM {fq('dq_genai_eval')})"""),
    ("ai_peril_vs_cause", "ai_classify peril vs. recorded cause code (sample of mismatches)",
     f"""SELECT claim_id, cause_of_loss, ai_peril, peril_consistent, pii_detected, loss_description_masked
         FROM {fq('silver_claims_ai_checked')} WHERE NOT peril_consistent LIMIT 10"""),
    ("bronze_to_gold_counts", "Row counts through the medallion",
     f"""SELECT 'bronze_fnol' layer, count(*) rows FROM {fq('bronze_fnol')} UNION ALL
         SELECT 'silver_claims', count(*) FROM {fq('silver_claims')} UNION ALL
         SELECT 'silver_claims_ai_checked', count(*) FROM {fq('silver_claims_ai_checked')} UNION ALL
         SELECT 'dq_claims_issues', count(*) FROM {fq('dq_claims_issues')} UNION ALL
         SELECT 'bronze_premium', count(*) FROM {fq('bronze_premium')} UNION ALL
         SELECT 'silver_premium', count(*) FROM {fq('silver_premium')} UNION ALL
         SELECT 'gold_daily_loss_run_lf', count(*) FROM {fq('gold_daily_loss_run_lf')}"""),
    ("reconciliation", "Reconciliation: Lakeflow gold vs. original gold over the landed window",
     f"""WITH lf AS (SELECT sum(incurred_loss) inc, sum(earned_premium) ep, min(as_of_date) d0, max(as_of_date) d1 FROM {fq('gold_daily_loss_run_lf')}),
              og AS (SELECT sum(incurred_loss) inc, sum(earned_premium) ep FROM {fq('gold_daily_loss_run')}, lf WHERE as_of_date BETWEEN lf.d0 AND lf.d1)
         SELECT lf.d0 from_date, lf.d1 to_date, round(lf.inc) lakeflow_incurred, round(og.inc) original_incurred,
                round(100 * (lf.inc - og.inc) / og.inc, 2) incurred_diff_pct,
                round(lf.inc / lf.ep, 4) lakeflow_loss_ratio, round(og.inc / og.ep, 4) original_loss_ratio FROM lf, og"""),
    ("rate_adequacy", "Rate adequacy per segment (Lakebase pricing + loss ratio vs target)",
     f"""SELECT line_of_business, region, loss_ratio_30d, target_loss_ratio, lr_gap_pts, indicated_rate_change_pct,
                achieved_rate_change_pct, rate_shortfall_pts, quotes, bind_ratio, referral_ratio, proposed_rate_actions, adequacy_status
         FROM {fq('gold_rate_adequacy')} ORDER BY rate_shortfall_pts DESC"""),
    ("watchlist_today", "Today's watchlist (the alert the coworker raised)",
     f"""SELECT line_of_business, region, status, primary_driver, round(lr_7d,3) lr_7d, round(lr_30d,3) lr_30d,
                round(target_loss_ratio,3) target, round(gap_7d_pts,1) gap_7d_pts FROM {fq('v_loss_ratio_watchlist')}
         WHERE status <> 'GREEN' ORDER BY gap_7d_pts DESC"""),
    ("action_status", "Team status of actions (snapshot of Lakebase ops.lr_actions)",
     f"""SELECT team, status, count(*) actions FROM {fq('lr_action_status')} GROUP BY ALL ORDER BY team, status"""),
    ("rate_actions", "Rate actions proposed to the pricing system (snapshot of Lakebase pricing.rate_actions)",
     f"SELECT rate_action_id, line_of_business, region, rate_change_pct, status, reason FROM {fq('bronze_rate_actions')}"),
]


def write_queries():
    (OUT / "csv").mkdir(parents=True, exist_ok=True)
    parts = ["# 04 · Query results (the business answers)\n",
             f"Run against `{CATALOG}.{SCHEMA}` on a serverless SQL warehouse at "
             f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}. Full results are in [`csv/`](csv/).\n"]
    results = {}
    for key, title, q in QUERIES:
        parts.append(f"\n## {title}\n\n<details><summary>SQL</summary>\n\n```sql\n{re.sub(r' +', ' ', q.strip())}\n```\n</details>\n")
        try:
            cols, rows = sql(q)
        except Exception as e:  # noqa: BLE001
            parts.append(f"_query failed: {str(e)[:300]}_\n")
            continue
        results[key] = (cols, rows)
        with open(OUT / "csv" / f"{key}.csv", "w", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(cols)
            wr.writerows(rows)
        parts.append(md_table(cols, rows) + "\n")
    (OUT / "04_query_results.md").write_text("\n".join(parts))
    return results


# ---------- 05 lakebase ----------
def write_lakebase(results):
    inst = cli("database", "get-database-instance", INSTANCE)
    try:
        st = cli("database", "get-synced-database-table", fq("lr_watchlist_serving"))
        sync = st.get("data_synchronization_status", {})
        sync_row = [st.get("name"), st.get("spec", {}).get("source_table_full_name"), sync.get("detailed_state"), sync.get("message", "")[:120]]
    except SystemExit as e:
        sync_row = [fq("lr_watchlist_serving"), "", "unavailable", str(e)[:120]]
    try:
        app = cli("apps", "get", APP)
        app_row = [app.get("name"), app.get("url"), app.get("app_status", {}).get("state"), app.get("compute_status", {}).get("state")]
    except SystemExit:
        app_row = [APP, "", "not deployed", ""]
    counts = results.get("action_status", (["team", "status", "actions"], []))
    body = f"""# 05 · Lakebase operational store and the Action Desk app

## Instance

| Name | State | Capacity | Postgres | Read/write DNS |
|---|---|---|---|---|
| `{inst.get('name')}` | {inst.get('state')} | {inst.get('capacity')} | {inst.get('pg_version', '')} | `{inst.get('read_write_dns', '')}` |

Defined in [`resources/lrc_lakebase.yml`](../../resources/lrc_lakebase.yml). Database `lrc_ops`, schemas `ops` and `pricing`
([`src/lakebase/01_setup_lakebase.py`](../../src/lakebase/01_setup_lakebase.py)).

## Synced table (Delta → Lakebase, for millisecond reads in the app)

{md_table(['Synced table', 'Source Delta table', 'State', 'Message'], [sync_row])}

## Action Desk app (Databricks App with a Lakebase database resource)

{md_table(['App', 'URL', 'App state', 'Compute'], [app_row])}

Source: [`app/action_desk/app.py`](../../app/action_desk/app.py). Screenshot: [`action_desk.png`](action_desk.png) (if captured).

## Team status of actions (Lakebase `ops.lr_actions`, snapshotted to Delta `lr_action_status`)

{md_table(*counts)}
"""
    (OUT / "05_lakebase.md").write_text(body)


# ---------- README ----------
def write_index(job, run, task_rows, exp_rows, results):
    ok = sum(1 for r in task_rows if r[3] == "SUCCESS")
    failed_exp = sum(int(r[3] or 0) for r in exp_rows)
    sc = results.get("dq_scorecard_latest", ([], []))[1]
    issues = results.get("dq_issues_by_check", ([], []))[1]
    genai = sum(int(r[3]) for r in issues if r[1] == "Gen AI")
    rule = sum(int(r[3]) for r in issues if r[1] != "Gen AI")
    rec = results.get("reconciliation", ([], [[None] * 7]))[1]
    rec = rec[0] if rec else [None] * 7
    ra = results.get("rate_adequacy", ([], []))
    ai = ra[0].index("adequacy_status") if "adequacy_status" in ra[0] else None
    inadequate = sum(1 for r in ra[1] if ai is not None and not str(r[ai]).startswith(("Adequate", "Monitor")))
    ga = results.get("genai_accuracy", ([], []))
    acc = "; ".join(f"{r[0]} ({r[1]}): precision {r[8]}, recall {r[9]}" for r in ga[1]) or "n/a"
    acts = sum(int(r[2]) for r in results.get("action_status", ([], []))[1])
    body = f"""# Run evidence: end-to-end daily run

Readable, committed output of one real run of the `lrc_end_to_end` Lakeflow Job in a Databricks workspace
(synthetic data only). Regenerate with `python deploy/collect_run_evidence.py` after a run.

| | |
|---|---|
| Run | `{run['run_id']}` · **{run['state'].get('result_state')}** · {ts(run.get('start_time'))} |
| Tasks | {ok}/{len(task_rows)} succeeded (notebooks + Lakeflow pipeline + Lakebase) |
| Lakeflow expectations | {len(exp_rows)} rule results recorded · {failed_exp:,} records failed a rule |
| Gen AI data-quality findings | {genai:,} (ai_classify peril mismatch, ai_mask personal data), each explained by ai_query |
| Gen AI accuracy vs seeded defects | {acc} |
| Rule-based findings | {rule:,} (negative amounts, loss after report, non-EUR currency) |
| Reconciliation | Lakeflow gold incurred differs from original gold by **{rec[4]}%** over {rec[0]} → {rec[1]} |
| Rate adequacy | {inadequate} segment(s) where the achieved rate change is below the indicated rate change |
| Lakebase actions | {acts} actions in `ops.lr_actions` with team status |

| File | What it shows |
|---|---|
| [01_job_run.md](01_job_run.md) | Task graph, result and duration per task |
| [02_notebook_outputs.md](02_notebook_outputs.md) | Code and real output of every notebook task |
| [03_lakeflow_pipeline.md](03_lakeflow_pipeline.md) | Pipeline datasets and expectation pass/fail counts from the event log |
| [04_query_results.md](04_query_results.md) | DQ scorecard, Gen AI findings, reconciliation, rate adequacy, watchlist |
| [05_lakebase.md](05_lakebase.md) | Lakebase instance, synced table, Action Desk app, team status |
| [csv/](csv/) | Query results as CSV |
"""
    (OUT / "README.md").write_text(body)


def redact() -> None:
    """Keep workspace-specific identifiers out of the committed evidence (host, catalog, user, app URL, emails)."""
    subs = [
        (re.compile(r"https://[a-z0-9.-]+\.databricksapps\.com"), "<app-url>"),
        (re.compile(r"https://[a-z0-9.-]+\.(cloud\.databricks\.com|azuredatabricks\.net|gcp\.databricks\.com)[^\s|)]*"), "<workspace-url>"),
        (re.compile(r"\[dev [^\]]+\] "), ""),
        (re.compile(r"[A-Za-z0-9._%+-]+@(?!example\.com)[A-Za-z0-9.-]+\.[a-z]{2,}"), "<user>"),
        (re.compile(r"/Users/[^/\s]+/"), "/Users/<user>/"),
        (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?=\))"), "<service-principal>"),
        (re.compile(r"instance-[0-9a-f-]+\.database\.[a-z0-9.]+"), "<lakebase-host>"),
    ]
    for f in OUT.rglob("*"):
        if f.suffix not in (".md", ".csv"):
            continue
        t = f.read_text().replace(CATALOG, "<catalog>")
        for rx, rep in subs:
            t = rx.sub(rep, t)
        f.write_text(t)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    job, run = latest_run()
    task_rows = write_job(job, run)
    write_notebooks(run)
    exp_rows = write_pipeline(run)
    results = write_queries()
    write_lakebase(results)
    write_index(job, run, task_rows, exp_rows, results)
    redact()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
