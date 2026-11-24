# Genie Loss Ratio Coworker

Manage an insurance loss ratio **daily, not monthly**, and learn how it is built on Databricks by running one notebook
at a time, in the order the data flows: synthetic source files → a Lakeflow pipeline (bronze, silver with data
quality, gold) → metric views → a Genie Agent and a dashboard → a Genie One morning brief → actions in Lakebase and a
Databricks App. All data is synthetic.

## Use case

The Chief Underwriting Officer of a European commercial P&C insurer (property, motor fleets, liability, marine across
five regions) is measured on the combined ratio against plan. Today, a deteriorating segment shows up in the month-end
pack three to six weeks after the claims arrived.

The coworker checks the book every morning instead:

1. **Trust the data.** Claim and premium files land in a raw volume. In the silver layer of a Lakeflow pipeline,
   Gen AI is part of the data-quality gate: it reads the free text that rules cannot, flags claims whose cause-of-loss
   code contradicts the description and personal data typed into the text, and explains each issue. Its verdicts are
   pipeline expectations next to the rule-based ones (dates, amounts, currency, duplicates). Unity Catalog masks that text and limits each claims team to
   its own region.
2. **Detect.** One governed loss-ratio definition marks each segment (line of business × region) RED, AMBER or GREEN
   on its 7-day and 30-day loss ratio against target, and names the driver: frequency, severity, catastrophe or a
   large loss.
3. **Explain and report.** A Genie Agent answers *why* in plain language, and a Genie One skill sends the morning brief
   to Slack and drafts one email per team.
4. **Act.** Each RED or AMBER segment maps to owned actions for Claims, Underwriting, Pricing, Reinsurance, Reserving
   and Finance. Teams work them in an app on Lakebase, and Pricing approves or rejects the proposed rate changes.

The synthetic book has three planted events for the coworker to find:

| Event | Segment | What the coworker should say |
|---|---|---|
| Hailstorm (last 6 days) | Property · DACH | RED, catastrophe: surge claims handling, notify cat reinsurers, book event IBNR |
| Frequency creep (last 3 weeks) | Motor · UK & Ireland | RED, frequency: review renewals and pricing, screen the claim cluster for fraud |
| One EUR 2.4m bodily-injury claim | Liability · Southern Europe | RED, large loss: senior handler, check the per-risk reinsurance attachment |

## Architecture

![Architecture](docs/architecture.png)

| Layer | Databricks feature | Notebooks |
|---|---|---|
| Landing | Unity Catalog volume with JSON claim files and CSV premium bordereaux | 00, 01 |
| Bronze | Lakeflow Spark Declarative Pipeline, streaming tables with Auto Loader | 02, `pipeline/01_bronze.sql` |
| Silver with Gen AI data quality | `ai_classify` and `ai_mask` as pipeline expectations next to the rules, `ai_query` explanations, Unity Catalog row filter and column mask | 03, `pipeline/02_silver.sql` |
| Gold | materialized view `gold_daily_loss_run` | 04, `pipeline/03_gold.sql` |
| One loss-ratio definition | metric views `mv_loss_ratio` and `mv_loss_run`, the watchlist view and the action playbook | 05 |
| Explain and report | Genie Agent, AI/BI dashboard, Genie One skill with Slack and email connectors | 06, 07, 08 |
| Act | Lakebase Postgres (actions, quotes, rate actions, synced table) and a Databricks App | 09 to 12 |

## Step-by-step guide

### Before you start

- A Unity Catalog workspace with **serverless** notebooks, SQL warehouses and Lakeflow pipelines, plus **Genie**,
  **Genie One**, **Lakebase**, **Databricks Apps** and **Foundation Model APIs** (for `ai_classify`, `ai_mask` and
  `ai_query`).
- A catalog you can create a schema in, or the privilege to create the catalog.
- The Lakebase instance (CU_1) and the app keep running until you delete them: see *Clean up*.

### Set up

1. In the workspace, go to **Workspace → Create → Git folder** and clone this repository.
2. Open `notebooks/00_setup`, set `CATALOG` (and `WAREHOUSE_ID` if you don't want the first serverless warehouse), and
   run it. Every other notebook runs `00_setup` first, so this is the only place you change settings.
3. Attach each notebook to **serverless** compute and use **Run all**. Run the steps in order and check the output
   before you move on.

### Run the steps

| Step | Notebook | What it does | Check before moving on |
|---|---|---|---|
| 0 | `00_setup` | Creates the catalog (if missing and allowed), the schema and the `raw` volume | It prints the target catalog, schema and volume |
| 1 | `01_generate_synthetic_data` | Generates the synthetic book and lands it as files: monthly files for the history, daily drops for the last 30 days, with the three planted events and planted data-quality defects | It prints the records and files landed, the events and the defects |
| 2 | `02_bronze` | Creates the Lakeflow pipeline with `pipeline/01_bronze.sql` and runs it: Auto Loader reads every file into `bronze_fnol` and `bronze_premium` | Records per table; open the pipeline graph from the printed link |
| 3 | `03_silver_data_quality` | Creates the row filter and column mask, adds `pipeline/02_silver.sql` and runs it: Gen AI checks (`ai_classify`, `ai_mask`) on the ~2,000 newest claims become expectations next to the rules, and `ai_query` explains every issue | The Gen AI and rule expectations side by side, the claims Gen AI flagged with their explanation, the masked text |
| 4 | `04_gold` | Adds `pipeline/03_gold.sql` and runs it: `gold_daily_loss_run`, one row per day, line of business and region | 7-day loss ratio by segment: Property DACH, Motor UK & Ireland and Liability Southern Europe at the top |
| 5 | `05_metric_views` | Targets, public benchmarks, the metric views, the RED/AMBER/GREEN watchlist, the action playbook and `v_todays_actions`, tags | The watchlist includes the three planted segments as RED (another can breach by chance) |
| 6 | `06_genie_agent` | Creates the **Loss Ratio Coworker** Genie Agent on the metric views, watchlist, actions and data-quality tables | Open the link and ask *"Why did DACH Property loss ratio jump this week?"* |
| 7 | `07_dashboard` | Creates and publishes the **Daily Loss Ratio Watch** AI/BI dashboard | Open the printed link |
| 8 | `08_genie_one_brief` | Instructions to create the `loss-ratio-daily-brief` skill in Genie One, run it, schedule it and connect Slack and email; a cell with today's governed numbers to compare | Genie One's brief matches the numbers in the notebook |
| 9 | `09_lakebase_setup` | Creates the Lakebase instance, the `lrc_ops` database, the `ops` and `pricing` schemas, and seeds quotes | The first run waits until the new instance is available |
| 10 | `10_publish_actions_and_pricing` | Publishes `v_todays_actions` into `ops.lr_actions`, records today's quotes and proposed rate actions in one Postgres transaction, syncs the watchlist to Lakebase | It prints the actions published and the synced table state |
| 11 | `11_action_desk_app` | Deploys the Streamlit **Action Desk** app on Lakebase and grants its service principal access | Open the app and set an action to IN_PROGRESS |
| 12 | `12_snapshot_to_delta` | Copies actions, quotes and rate actions back to Delta, and builds `gold_rate_adequacy` (indicated vs achieved rate change) | Your app change appears in `lr_action_status` |
| 13 | `13_refresh_genie_agent` | Re-runs step 06 so the agent also covers team status and rate adequacy | Ask *"Which actions are still open for Reinsurance?"* |

If you re-run step 01, set `FULL_REFRESH = True` in `00_setup` for the next pipeline run (steps 02 to 04), then set it
back to `False`.

### Optional modules (not needed for the main flow)

| Notebook | What it does | Run after |
|---|---|---|
| `optional/ml_frequency_forecast` | Trains a next-7-day claim-frequency model on the gold table, registers it in Unity Catalog and escalates rising segments whose Lakebase action is still open | step 04 (step 12 for the escalations) |
| `optional/genie_why_and_llm_judge` | Asks the Genie Agent *why* for each RED or AMBER segment through the Conversation API, then has an independent model grade each answer into `lr_explanation_judge` | step 06 |
| `optional/evaluate_genai_dq` | Scores the Gen AI data-quality checks against the planted defects (precision, recall, F1) and has an LLM judge grade the `ai_query` explanations | step 03 |

### Clean up

Delete what the notebooks created, in this order: the `lrc-action-desk` app, the `lrc-lakebase` Lakebase instance,
the `[LRC] Loss ratio pipeline`, the dashboard, the Genie Agent, the Genie One skill, the `lrc_frequency_forecast`
model if you ran the ML module, and finally the schema: `DROP SCHEMA <catalog>.loss_ratio_coworker CASCADE`.
