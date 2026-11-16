"""CUO benchmark for the deployed Genie Agent: ask, capture Genie's SQL and result, score against ground-truth SQL.

Each question has a ground-truth query on the governed tables. The harness asks the Loss Ratio Coworker Genie Agent
through the Genie Conversation API, fetches the SQL Genie generated and its result, and passes the question if every
expected value appears in Genie's result (numbers within tolerance, ratios accepted as 0.62 or 62%).

Writes docs/run_evidence/06_genie_agent.md and csv/genie_benchmark.csv (appended to the run evidence).

Usage: LRC_CATALOG=... LRC_WAREHOUSE_ID=... DATABRICKS_CONFIG_PROFILE=... python deploy/genie_benchmark.py
"""
from __future__ import annotations

import csv
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from common import AGENT_TITLE, CATALOG, cli, fq
from collect_run_evidence import OUT, md_table, redact, sql

QUESTIONS = [
    ("Which line of business and region segments are RED today?",
     f"SELECT line_of_business, region FROM {fq('v_loss_ratio_watchlist')} WHERE status = 'RED'"),
    ("What is the 30-day loss ratio for Property in DACH?",
     f"SELECT lr_30d FROM {fq('v_loss_ratio_watchlist')} WHERE line_of_business = 'Property' AND region = 'DACH'"),
    ("What is the year-to-date loss ratio for Liability in Southern Europe?",
     f"SELECT lr_ytd FROM {fq('v_loss_ratio_watchlist')} WHERE line_of_business = 'Liability' AND region = 'Southern Europe'"),
    ("What is the primary driver of the Motor loss ratio in UK & Ireland?",
     f"SELECT primary_driver FROM {fq('v_loss_ratio_watchlist')} WHERE line_of_business = 'Motor' AND region = 'UK & Ireland'"),
    ("What is the target loss ratio for Marine?",
     f"SELECT target_loss_ratio FROM {fq('lr_targets')} WHERE line_of_business = 'Marine'"),
    ("Which team owns the Property line of business?",
     f"SELECT owner_team FROM {fq('lr_targets')} WHERE line_of_business = 'Property'"),
    ("Which data-quality check found the most issues on the latest report date?",
     f"SELECT check_name FROM {fq('dq_daily_scorecard')} WHERE report_date = (SELECT MAX(report_date) FROM {fq('dq_daily_scorecard')}) ORDER BY issues DESC LIMIT 1"),
    ("How many claims with personal data in the description were found in total?",
     f"SELECT COUNT(DISTINCT claim_id) FROM {fq('dq_claims_issues')} WHERE check_name = 'pii_in_free_text'"),
    ("How many Reinsurance actions are not done yet?",
     f"SELECT COUNT(*) FROM {fq('lr_action_status')} WHERE team = 'Reinsurance' AND status <> 'DONE'"),
    ("Which segments are rate inadequate, with the achieved rate change below the indicated rate change and no rate action?",
     f"SELECT line_of_business, region FROM {fq('gold_rate_adequacy')} WHERE adequacy_status LIKE 'Rate inadequate%'"),
]


def genie_space_id() -> str:
    spaces = cli("genie", "list-spaces").get("spaces", [])
    return next(s["space_id"] for s in spaces if s.get("title") == AGENT_TITLE)


def ask(space: str, question: str) -> dict:
    base = f"/api/2.0/genie/spaces/{space}"
    st = cli("api", "post", f"{base}/start-conversation", body={"content": question})
    cid, mid = st["conversation_id"], st["message_id"]
    msg = {}
    for _ in range(80):
        msg = cli("api", "get", f"{base}/conversations/{cid}/messages/{mid}")
        if msg.get("status") in ("COMPLETED", "FAILED", "CANCELLED"):
            break
        time.sleep(3)
    out = {"status": msg.get("status"), "sql": "", "text": "", "cols": [], "rows": []}
    for a in msg.get("attachments") or []:
        if a.get("text", {}).get("content"):
            out["text"] += a["text"]["content"].strip() + " "
        if a.get("query"):
            out["sql"] = a["query"].get("query", "")
            out["text"] += (a["query"].get("description") or "") + " "
            try:
                qr = cli("api", "get", f"{base}/conversations/{cid}/messages/{mid}/attachments/{a['attachment_id']}/query-result")
                sr = qr.get("statement_response", {})
                out["cols"] = [c["name"] for c in sr.get("manifest", {}).get("schema", {}).get("columns", [])]
                out["rows"] = sr.get("result", {}).get("data_array", []) or []
            except SystemExit as e:
                out["text"] += f"(result unavailable: {str(e)[:120]})"
    return out


def matches(expected: str, cells: list[str], text: str) -> bool:
    try:
        x = float(expected)
        for c in cells + re.findall(r"-?\d+(?:\.\d+)?", text):
            try:
                v = float(str(c).replace("%", "").replace(",", ""))
            except ValueError:
                continue
            if abs(v - x) <= max(0.0051, abs(x) * 0.005) or abs(v - 100 * x) <= 0.51 or abs(v / 100 - x) <= 0.0051:
                return True
        return False
    except ValueError:
        e = expected.lower()
        return any(e == str(c).lower() for c in cells) or e in text.lower()


def main():
    space = genie_space_id()
    rows, parts = [], []
    for i, (q, truth_sql) in enumerate(QUESTIONS, 1):
        _, truth = sql(truth_sql)
        expected = [str(v) for r in truth for v in r if v is not None]
        g = ask(space, q)
        cells = [str(v) for r in g["rows"] for v in r if v is not None]
        ok = bool(expected) and all(matches(e, cells, g["text"]) for e in expected)
        rows.append([i, q, "PASS" if ok else "FAIL", "; ".join(expected), g["status"]])
        parts.append(f"\n## Q{i}. {q}\n\n**Result: {'✅ PASS' if ok else '❌ FAIL'}** · expected `{', '.join(expected)}`\n")
        if g["text"].strip():
            parts.append(f"> Genie: {g['text'].strip()[:600]}\n")
        if g["sql"]:
            parts.append(f"<details><summary>SQL generated by Genie</summary>\n\n```sql\n{g['sql'].strip()}\n```\n</details>\n")
        if g["cols"]:
            parts.append("Genie's query result:\n\n" + md_table(g["cols"], g["rows"], 12) + "\n")
        print(f"Q{i} {'PASS' if ok else 'FAIL'}: {q}")
    passed = sum(r[2] == "PASS" for r in rows)
    head = f"""# 06 · Genie Agent: live answers and CUO benchmark

The deployed **{AGENT_TITLE}** Genie Agent was asked {len(rows)} questions through the Genie Conversation API on
{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}. Each answer is scored against a ground-truth SQL query on the same
governed tables ([`deploy/genie_benchmark.py`](../../deploy/genie_benchmark.py)).

**Score: {passed}/{len(rows)} ({100 * passed / len(rows):.0f}%)** · go-live target in the rollout plan: ≥ 90% on a 20-question CUO benchmark.

{md_table(['#', 'Question', 'Result', 'Expected (ground truth)', 'Genie status'], rows, 50)}
"""
    (OUT / "06_genie_agent.md").write_text(head + "\n".join(parts) + "\n")
    (OUT / "csv").mkdir(exist_ok=True)
    with open(OUT / "csv" / "genie_benchmark.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["n", "question", "result", "expected", "genie_status"]); w.writerows(rows)
    idx = OUT / "README.md"
    t = idx.read_text()
    line = f"| Genie Agent benchmark | {passed}/{len(rows)} questions answered correctly from the governed tables ([06_genie_agent.md](06_genie_agent.md)) |\n"
    t = re.sub(r"\| Genie Agent benchmark \|.*\n", "", t)
    t = t.replace("| Lakebase actions |", line + "| Lakebase actions |", 1)
    if "06_genie_agent.md" not in t.split("| File |")[1]:
        t = t.replace("| [csv/](csv/) |", "| [06_genie_agent.md](06_genie_agent.md) | Live Genie Agent answers: question, Genie's SQL, result, pass/fail |\n| [csv/](csv/) |")
    idx.write_text(t)
    redact()
    print(f"score {passed}/{len(rows)}")


if __name__ == "__main__":
    main()
