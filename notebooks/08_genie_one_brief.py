# Databricks notebook source
# MAGIC %md
# MAGIC # 08 · Genie One: the morning loss-ratio brief
# MAGIC
# MAGIC Genie One is the assistant that reports to people where they work. Here it becomes the coworker's voice: a **skill**
# MAGIC that reads the governed views through the Loss Ratio Coworker Genie Agent and writes the morning brief, then posts it
# MAGIC to Slack and drafts one email per team. Nothing in this step needs code: you set it up in Genie One.
# MAGIC
# MAGIC ### 1 · Create the skill
# MAGIC Open **Genie One** and say: *Create a skill called `loss-ratio-daily-brief` with these instructions*, then paste:
# MAGIC
# MAGIC > **When to use:** the user asks for the morning loss-ratio brief, "how is the loss ratio today", "what's red" or
# MAGIC > "what should my team do about the loss ratio".
# MAGIC >
# MAGIC > 1. Use the **Loss Ratio Coworker** Genie Agent. Never compute the loss ratio from raw tables: use `mv_loss_ratio`.
# MAGIC > 2. Read `v_loss_ratio_watchlist` for today. List every RED segment, then AMBER, with the 7-day and 30-day loss ratio,
# MAGIC >    the target, the gap in points and `primary_driver`. If the user named a line of business or region, filter to it.
# MAGIC > 3. For each RED segment, explain **why** in one sentence: frequency vs severity, the top cause of loss and any event
# MAGIC >    or large loss (from `mv_loss_run`).
# MAGIC > 4. Read `v_todays_actions` and group the actions **by team**, with priority and due date.
# MAGIC > 5. Add one data-quality line from `dq_daily_scorecard` (claims flagged by the Gen AI checks).
# MAGIC > 6. Close with the year-to-date loss ratio and combined ratio vs target, and vs `industry_benchmarks` (name the
# MAGIC >    source; benchmarks are context, not targets).
# MAGIC > 7. **Slack:** post the executive version to `#exec-loss-ratio`. **Email:** create one **draft** per team with P1 or
# MAGIC >    P2 actions, addressed to the team lead. Only create drafts, never send.
# MAGIC >
# MAGIC > Rules: never invent numbers; ratios as percentages with one decimal; money in EUR with k/m; if nothing is RED or
# MAGIC > AMBER, say "No loss-ratio alerts today" and give the book line only.
# MAGIC
# MAGIC ### 2 · Run it, then schedule it
# MAGIC - Run it on demand: `/loss-ratio-daily-brief`, or `/loss-ratio-daily-brief Motor`.
# MAGIC - Schedule it: *Run /loss-ratio-daily-brief every weekday at 07:30 Europe/London*.
# MAGIC - For steps 7 of the skill, connect **Slack** and **Gmail** or **Microsoft 365** in Genie One. Posting and drafting
# MAGIC   use the connectors' write tools, which an admin may need to enable. Without them, the brief still appears in Genie One.
# MAGIC
# MAGIC ### 3 · Check it against the governed numbers
# MAGIC The next cell shows what the brief should say today. The numbers in Genie One's answer must match it.

# COMMAND ----------

# MAGIC %run ./00_setup

# COMMAND ----------

display(spark.sql(f"""SELECT status, line_of_business, region, primary_driver, ROUND(lr_7d * 100, 1) AS lr_7d_pct,
                             ROUND(lr_30d * 100, 1) AS lr_30d_pct, ROUND(target_loss_ratio * 100, 1) AS target_pct, gap_7d_pts
                      FROM {FQ}.v_loss_ratio_watchlist WHERE status <> 'GREEN' ORDER BY status DESC, gap_7d_pts DESC"""))
display(spark.sql(f"SELECT team, priority, line_of_business, region, action, due_within FROM {FQ}.v_todays_actions ORDER BY team, priority"))
