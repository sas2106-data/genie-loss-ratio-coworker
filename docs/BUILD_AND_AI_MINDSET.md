# Build and AI mindset: workflow, decisions, trade-offs, and the evidence that it ran

Every number on this page is copied from committed run output of the Lakeflow Job `lrc_end_to_end`
(run `945039689803583`, 2026-11-16, 11/11 tasks SUCCESS). The raw files are in [`run_evidence/`](run_evidence/):
executed notebooks with their cell outputs ([`run_evidence/notebooks/`](run_evidence/notebooks/)), a plain-text job log
([`job_run_log.txt`](run_evidence/job_run_log.txt)), the Lakeflow event log
([`pipeline_event_log.txt`](run_evidence/pipeline_event_log.txt)) and query results as Markdown and CSV.

## 1 · Tools

| Tool | Used for |
|---|---|
| **Claude Code** with Databricks skills (bundles, Lakebase, Apps, Genie) and the Databricks CLI | writing and debugging the notebooks, pipeline SQL, app and bundle; reading run output and event logs |
| **Declarative Automation Bundle** ([`databricks.yml`](../databricks.yml)) | every resource as code: Lakebase instance, Lakeflow pipeline, Databricks App, 3 Lakeflow Jobs |
| **Lakeflow Spark Declarative Pipelines**, Auto Loader, expectations | ingestion and transformation ([`src/pipeline/lrc_ingest_pipeline.sql`](../src/pipeline/lrc_ingest_pipeline.sql)) |
| **AI Functions** `ai_classify`, `ai_mask`, `ai_query` on Foundation Model APIs | data quality on free text inside the pipeline; LLM judge in the daily watch and the evaluation notebook |
| **Genie Agent** + Genie Conversation API, **Genie One** | explain *why*; benchmark harness ([`deploy/genie_benchmark.py`](../deploy/genie_benchmark.py)) |
| **Lakebase** (Postgres), synced tables, **Databricks Apps** | operational store for actions, team status and pricing; Action Desk app |
| **MLflow** + Unity Catalog model registry | claim-frequency forecast `lrc_frequency_forecast@champion` |
| **Unity Catalog** row filters, column masks, metric views | one governed definition; region and GDPR policies enforced in the catalog |

## 2 · Workflow

1. **Define the number once**: loss ratio = incurred ÷ earned in a metric view, with targets, thresholds and owners.
2. **Seed the truth**: synthetic data with three events (hailstorm, motor frequency creep, a EUR 2.4m bodily-injury loss)
   and deliberately injected data-quality defects, so every AI finding can be scored against ground truth.
3. **Build everything as code** in one bundle and run it as one job, every time end to end.
4. **Measure before trusting**: precision/recall of the AI checks, an independent LLM judge of every explanation, a
   ground-truth benchmark for Genie, a reconciliation of the Lakeflow gold against the original, a naive baseline for the model.
5. **Fix what the measurement shows**, re-run the whole job, and commit the output (not a summary of it).

## 3 · Decisions and trade-offs, each with the measurement behind it

| # | Decision | Trade-off | What the run shows |
|---|---|---|---|
| 1 | **Rules decide, Genie explains.** RED/AMBER and the action playbook are deterministic; the LLM never sets a status | Less "clever", fully auditable | `recorded 6 alerts and 16 actions` (watch notebook output) |
| 2 | **Measure the explanations, don't assume them.** An independent model (Claude Sonnet) judges every Genie explanation stored in `lr_alerts` | One more model call per alert | Genie explanations: avg **3.14/5**, grounded **81%**, names the driver **72%**: a real gap, now tracked daily in `lr_explanation_judge` |
| 3 | **Gen AI checks inside the pipeline**, in SQL on governed data, not an external LLM service | Bound cost to the last 14 report days | 1,981 claims checked by `ai_classify` and `ai_mask` |
| 4 | **Drop the `address` label from `ai_mask`** | Addresses typed in free text are no longer masked by AI (the column mask still redacts phones, emails and contact names) | Before: ≈92% of claims flagged (city names masked). After: personal-data precision **78.7%**, recall **100%** |
| 5 | **Tune the peril → cause mapping, not a threshold**: a storm at sea damaging cargo is consistent with Heavy Weather | A broader mapping could hide a real mismatch, so every seeded mismatch was re-checked | Peril precision **45% → 95.5%**, recall **100%** (21 of 21 seeded mismatches caught, 1 false alarm) |
| 6 | **Fix Genie with context, not a new model** | Instructions must be maintained as tables are added | Benchmark 9/10 → 10/10 twice: once naming the DQ check values, once pinning the loss ratio to the governed view after Genie answered from a pipeline table (97.1% instead of the governed 98.1%) |
| 7 | **Lakebase for rows people change, Delta for analytics** | A Postgres → Delta snapshot step | `Lakebase ops.lr_actions: 0 new actions published, 16 already there (team updates kept)`; Claims shows 1 ACKNOWLEDGED and 1 IN_PROGRESS from the app |
| 8 | **Enforce GDPR and regional access in Unity Catalog**, not in each report | Admin-bypass rule must be kept tight | 2 row filters + 1 column mask attached (information_schema); non-PII readers see `Contact [name] on [phone] or [email]` |
| 9 | **A model must beat a naive baseline to be promoted** | More code than "train and register" | hold-out MAE **5.44 vs 6.84** claims/week (**+20.4%**) → `lrc_frequency_forecast v3 → alias champion` |
| 10 | **Reconcile the new pipeline against the old gold** | Small, explained differences instead of silent ones | Lakeflow gold incurred −2.99% vs original over 30 days (rejected negative and non-EUR claims); loss ratio 67.2% vs 67.1% |
| 11 | **A person on the send button** | Slower than auto-send | Gmail connector drafts only; webhooks in `dry_run` |

What did not work first time, and is fixed in the committed code:
- an inline `--` comment in the pipeline SQL swallowed the `AS loss_description_masked` alias (pipeline failed; fixed);
- the synced table is created asynchronously, so the app's first grant missed it ("permission denied"); the grant now
  waits for ONLINE and is re-applied in the snapshot step;
- `ai_query` explanations scored **72.5% faithful** by the judge: for negative amounts it advises "make it positive"
  and ignores legitimate recoveries. Next step: add claim status and recovery fields to the prompt.

## 4 · Execution evidence (verbatim)

**Job run log** (`docs/run_evidence/job_run_log.txt`)

```text
Lakeflow Job run 945039689803583  result=SUCCESS  start=2026-11-16 05:50:41 UTC  end=2026-11-16 06:08:34 UTC

2026-11-16 05:50:41 UTC  governance_policies              notebook  SUCCESS      42s  depends_on=-
2026-11-16 05:50:41 UTC  generate_loss_run                notebook  SUCCESS      45s  depends_on=-
2026-11-16 05:50:41 UTC  lakebase_setup                   notebook  SUCCESS      37s  depends_on=-
2026-11-16 05:51:26 UTC  land_raw_files                   notebook  SUCCESS      72s  depends_on=generate_loss_run
2026-11-16 05:51:26 UTC  semantic_layer                   notebook  SUCCESS      40s  depends_on=generate_loss_run,governance_policies
2026-11-16 05:52:06 UTC  watch_and_explain                notebook  SUCCESS     554s  depends_on=semantic_layer,lakebase_setup
2026-11-16 06:01:21 UTC  lakebase_publish_and_transact    notebook  SUCCESS      27s  depends_on=watch_and_explain
2026-11-16 06:01:48 UTC  lakebase_snapshot_to_delta       notebook  SUCCESS      28s  depends_on=lakebase_publish_and_transact
2026-11-16 06:02:17 UTC  lakeflow_ingest_and_ai_dq        pipeline  SUCCESS     315s  depends_on=land_raw_files,lakebase_snapshot_to_delta,governance_policies
2026-11-16 06:02:17 UTC  train_frequency_forecast         notebook  SUCCESS      90s  depends_on=semantic_layer,lakebase_snapshot_to_delta
2026-11-16 06:07:32 UTC  evaluate_genai_dq                notebook  SUCCESS      62s  depends_on=lakeflow_ingest_and_ai_dq
```

**Notebook cell outputs** (from `docs/run_evidence/notebooks/*.ipynb`)

```text
[02 generate_loss_run]   wrote claims 77,527 rows · As of 2026-11-16: book loss ratio 63.3% | seeded events: 238 hail, 120 motor, 1 large BI
[03 lakebase_setup]      Lakebase instance lrc-lakebase · database lrc_ops · schemas ops, pricing and tables ready
                         ops.lr_actions 16 · pricing.quotes 24300 · pricing.rate_actions 2
[04 land_raw_files]      Landed 30 days (2026-10-18 → 2026-11-16) · claims 3750 · seeded: mismatch 42, pii 137, neg 15
[06 watch_and_explain]   6 segments need attention | book YTD LR 63.6%, COR 92.1% vs industry 92.9%
                         recorded 6 alerts and 16 actions
                         Lakebase ops.lr_actions: 0 new actions published, 16 already there (team updates kept)
                           Claims ACKNOWLEDGED 1 · Claims IN_PROGRESS 1 · Claims OPEN 2 · Finance OPEN 1 · Pricing OPEN 2 ...
[07 publish_and_transact] synced table state: SYNCED_TABLE_ONLINE_UPDATING_PIPELINE_RESOURCES
                         granted app lrc-action-desk access to ops, pricing and synced schema loss_ratio_coworker
[08 snapshot_to_delta]   lr_action_status: 16 rows · bronze_pricing_quotes: 24,300 rows · bronze_rate_actions: 2 rows
[09 frequency_forecast]  1,700 weekly rows · 20 segments · 20 features
                         hold-out MAE: model 5.44 vs naive 6.84 claims/week → +20.4% better than naive
                         lrc_frequency_forecast v3 → alias champion
```

**LLM judge of the Genie explanations** (watch notebook, table `lr_explanation_judge`)

| alert_id | primary_driver | grounded | names_driver | actionable | score | reason (judge, verbatim) |
|---|---|---|---|---|---|---|
| LR-20261116-PRO-DACH | Catastrophe event | True | True | True | 4 | Figures match the FACTS and the 205.9-point gap is correct; '+5.198x' is ambiguous (the ratio is about 6.2x), but the hail event is clearly named. |
| LR-20261116-LIA-SOUT | Large loss | True | True | True | 4 | Figures match the FACTS and large loss is named. The 4.0% frequency rise is slightly off (about 3.9%). The next step is implied rather than stated. |

**Lakeflow expectations** (pipeline event log)

| Dataset | Expectation | Passed | Failed |
|---|---|---|---|
| silver_claims | currency_is_eur | 3702 | 14 |
| silver_claims | non_negative_amount | 3701 | 15 |
| silver_premium | positive_premium | 590 | 10 |

**Gen AI checks against seeded defects** (`dq_genai_eval`)

| check | function | claims checked | seeded | flagged | TP | FP | FN | precision | recall | F1 |
|---|---|---|---|---|---|---|---|---|---|---|
| peril_mismatch | ai_classify | 1981 | 21 | 22 | 21 | 1 | 0 | 0.955 | 1.0 | 0.977 |
| pii_in_free_text | ai_mask | 1981 | 70 | 89 | 70 | 19 | 0 | 0.787 | 1.0 | 0.881 |

**LLM judge of the ai_query explanations** (`dq_explanation_judge`, 40 judged)

| check | judged | correct check | actionable | no personal data | faithful | avg score |
|---|---|---|---|---|---|---|
| peril_mismatch | 6 | 1.0 | 1.0 | 1.0 | 1.0 | 4.83 |
| pii_in_free_text | 28 | 0.75 | 0.964 | 1.0 | 0.821 | 3.21 |
| all | 40 | 0.825 | 0.975 | 1.0 | 0.725 | 3.38 |

**Genie Agent benchmark**: 10/10 questions answered correctly against ground-truth SQL; each question, Genie's SQL and
its result are in [`run_evidence/06_genie_agent.md`](run_evidence/06_genie_agent.md).
