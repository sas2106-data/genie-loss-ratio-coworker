"""Create or update the "Loss Ratio Coworker" Genie Agent.

The agent sits on the governed metric views, so Genie answers with the same loss ratio as the dashboard and the alert job.
Genie One routes loss-ratio questions to this agent, and Slack or Teams channels can pin it.

    LRC_CATALOG=... LRC_WAREHOUSE_ID=... DATABRICKS_CONFIG_PROFILE=... python deploy/genie_agent.py
"""
from __future__ import annotations

import json

from common import AGENT_TITLE, PARENT_PATH, WAREHOUSE_ID, cli, fq, new_id

DESCRIPTION = ("Daily loss-ratio watch for a European commercial P&C book (synthetic data). Ask about loss ratio vs "
               "target, frequency vs severity, large and catastrophe losses, and the actions recommended to each team.")

TABLES = {
    "mv_loss_ratio": "Governed metric view. Use for loss ratio, combined ratio, target gap, frequency, severity by day/LOB/region.",
    "mv_loss_run": "Governed metric view of the claim-level loss run by cause of loss, event, status and large-loss flag.",
    "v_loss_ratio_watchlist": "Today's RED/AMBER/GREEN watch per line of business and region with 7-day, 30-day and YTD loss ratio and the main driver.",
    "lr_action_recommendations": "Actions recommended to downstream teams (Claims, Underwriting, Pricing, Reinsurance, Reserving, Finance) for each alert.",
    "lr_alerts": "History of daily loss-ratio alerts with Genie's explanation.",
    "industry_benchmarks": "Public combined-ratio benchmarks (AM Best US P&C industry, Global Insurance Customer P&C) with sources.",
    "lr_targets": "Plan loss ratio, expense ratio, alert thresholds and owner team per line of business.",
}

# Added when the Lakeflow / Gen AI / Lakebase scenario has run (resources/lrc_jobs.yml → lrc_end_to_end)
EXTENDED_TABLES = {
    "dq_daily_scorecard": "Daily data-quality scorecard from the Lakeflow pipeline: records checked, issues and pass rate per check (rule-based and Gen AI).",
    "dq_claims_issues": "One row per claim data-quality issue (peril mismatch found by ai_classify, personal data found by ai_mask, negative amounts, date and currency errors) with an ai_query explanation and suggested fix. Personal data is masked.",
    "lr_action_status": "Team status of each loss-ratio action (OPEN, ACKNOWLEDGED, IN_PROGRESS, DONE) with owner and note, snapshotted from the Lakebase operational store.",
    "gold_rate_adequacy": "Rate adequacy per line of business and region: 30-day loss ratio vs target, quotes, bind ratio and average rate change from the Lakebase pricing system, and proposed rate actions.",
    "gold_daily_loss_run_lf": "Daily loss run built by the Lakeflow pipeline from the raw files (same shape as gold_daily_loss_run).",
}

INSTRUCTIONS = """\
You are the loss-ratio coworker for the CUO, CFO and underwriting leaders of a European commercial P&C insurer. Currency is EUR. Data is synthetic.

Definitions (always use these):
- Loss ratio = incurred loss / earned premium, on the reported (as-of) basis. Use MEASURE(loss_ratio) from mv_loss_ratio. Never average ratios across rows.
- Combined ratio = loss ratio + planned expense ratio. Below 100% is an underwriting profit.
- "Today" is the latest as_of_date in the data. "This week" means the last 7 days, "this month" the last 30 days unless the user says calendar month.
- Frequency = claims per EUR 1m earned premium. Severity = incurred loss per claim. Large loss = incurred of EUR 250k or more.

How to answer:
- Lead with the number and its gap to target in percentage points, then the driver, then what to do.
- When asked "why", split the change into frequency versus severity and name the top causes of loss, events and large losses from mv_loss_run.
- When asked "what should we do" or "who needs to act", read lr_action_recommendations for the latest alerts and group by team.
- When asked how we compare with the market, use industry_benchmarks and always name the source and basis (e.g. AM Best FY2025 US P&C 92.9%). Do not present benchmarks as targets.
- Format ratios as percentages with one decimal and money as EUR with k/m suffixes. Keep answers short enough to read on a phone.
- Data quality: use dq_daily_scorecard for pass rates and dq_claims_issues for the issues and their ai_explanation. Never show unmasked personal data.
- Team status: use lr_action_status for whether an action is OPEN, ACKNOWLEDGED, IN_PROGRESS or DONE, its owner and note (updated by teams in the Action Desk app on Lakebase).
- Pricing: use gold_rate_adequacy for rate adequacy, bind ratio and proposed rate actions per segment.
"""

SAMPLE_QUESTIONS = [
    "Which lines of business are RED or AMBER on loss ratio today?",
    "Why did DACH Property loss ratio jump this week?",
    "Is UK & Ireland Motor deteriorating because of frequency or severity?",
    "What actions are recommended for the Claims team today?",
    "How does our year-to-date combined ratio compare with the US P&C industry and the Global Insurance Customer?",
    "Show the 30-day loss ratio by line of business against target.",
]
EXTENDED_QUESTIONS = [
    "Which data-quality checks failed today and why?",
    "Which actions are still open for Reinsurance and who owns them?",
    "Where is the loss ratio above target with no rate increase?",
]

EXAMPLE_SQL = [
    ("What is our loss ratio by line of business this year versus target?",
     f"SELECT line_of_business, MEASURE(loss_ratio) AS loss_ratio, MEASURE(target_loss_ratio) AS target, "
     f"MEASURE(loss_ratio_vs_target_pts) AS gap_pts FROM {fq('mv_loss_ratio')} "
     f"WHERE YEAR(as_of_date) = YEAR((SELECT MAX(as_of_date) FROM {fq('gold_daily_loss_run')})) "
     f"GROUP BY line_of_business ORDER BY gap_pts DESC"),
    ("Which segments need attention today?",
     f"SELECT line_of_business, region, status, primary_driver, lr_7d, lr_30d, target_loss_ratio, gap_7d_pts "
     f"FROM {fq('v_loss_ratio_watchlist')} WHERE status <> 'GREEN' ORDER BY gap_7d_pts DESC"),
    ("What are the top causes of loss in the last 7 days?",
     f"SELECT line_of_business, region, cause_of_loss, event_tag, MEASURE(claim_count) AS claims, "
     f"MEASURE(incurred_loss) AS incurred FROM {fq('mv_loss_run')} "
     f"WHERE report_date > (SELECT MAX(report_date) FROM {fq('claims')}) - INTERVAL 7 DAYS "
     f"GROUP BY ALL ORDER BY incurred DESC LIMIT 10"),
]


def _exists(name: str) -> bool:
    try:
        cli("tables", "get", fq(name))
        return True
    except SystemExit:
        return False


def serialized_space() -> dict:
    tables = dict(TABLES)
    extra = {t: d for t, d in EXTENDED_TABLES.items() if _exists(t)}
    tables.update(extra)
    questions = SAMPLE_QUESTIONS + (EXTENDED_QUESTIONS if extra else [])
    examples = list(EXAMPLE_SQL)
    if "dq_daily_scorecard" in extra:
        examples.append(("Which data-quality checks failed today and why?",
                         f"SELECT s.check_name, s.check_type, s.issues, s.pass_rate, ANY_VALUE(i.ai_explanation) AS example_explanation "
                         f"FROM {fq('dq_daily_scorecard')} s LEFT JOIN {fq('dq_claims_issues')} i USING (report_date, check_name) "
                         f"WHERE s.report_date = (SELECT MAX(report_date) FROM {fq('dq_daily_scorecard')}) GROUP BY ALL ORDER BY s.issues DESC"))
    if "lr_action_status" in extra:
        examples.append(("Which actions are still open for Reinsurance?",
                         f"SELECT line_of_business, region, priority, action, due_within, status, owner, note FROM {fq('lr_action_status')} "
                         f"WHERE team = 'Reinsurance' AND status <> 'DONE' ORDER BY priority, as_of_date DESC"))
    return {
        "version": 2,
        "config": {"sample_questions": sorted(
            [{"id": new_id(), "question": [q]} for q in questions], key=lambda x: x["id"])},
        "data_sources": {"tables": sorted(
            [{"identifier": fq(t), "description": [d]} for t, d in tables.items()], key=lambda x: x["identifier"])},
        "instructions": {
            "text_instructions": [{"id": new_id(), "content": [INSTRUCTIONS]}],
            "example_question_sqls": sorted(
                [{"id": new_id(), "question": [q], "sql": [s]} for q, s in examples], key=lambda x: x["id"]),
        },
    }


def main() -> None:
    space = json.dumps(serialized_space())
    existing = [s for s in cli("genie", "list-spaces").get("spaces", []) if s.get("title") == AGENT_TITLE]
    if existing:
        sid = existing[0]["space_id"]
        cli("genie", "update-space", sid, "--serialized-space", space, "--title", AGENT_TITLE, "--description", DESCRIPTION)
        print(f"updated Genie Agent {sid}")
    else:
        args = ["genie", "create-space", WAREHOUSE_ID, space, "--title", AGENT_TITLE, "--description", DESCRIPTION]
        if PARENT_PATH:
            args += ["--parent-path", PARENT_PATH]
        sid = cli(*args)["space_id"]
        print(f"created Genie Agent {sid}")
    print(f"GENIE_SPACE_ID={sid}")


if __name__ == "__main__":
    main()
