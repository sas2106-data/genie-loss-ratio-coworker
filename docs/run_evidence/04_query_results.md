# 04 · Query results (the business answers)

Run against `<catalog>.loss_ratio_coworker` on a serverless SQL warehouse at 2026-11-16 05:21 UTC. Full results are in [`csv/`](csv/).


## Data-quality scorecard, latest report date (rule-based + Gen AI checks)

<details><summary>SQL</summary>

```sql
SELECT report_date, check_name, check_type, severity, issues, records_checked, pass_rate
 FROM <catalog>.loss_ratio_coworker.dq_daily_scorecard WHERE report_date = (SELECT MAX(report_date) FROM <catalog>.loss_ratio_coworker.dq_daily_scorecard)
 ORDER BY issues DESC
```
</details>

| report_date | check_name | check_type | severity | issues | records_checked | pass_rate |
|---|---|---|---|---|---|---|
| 2026-11-16 | pii_in_free_text | Gen AI | High | 4 | 148 | 0.973 |
| 2026-11-16 | negative_amount | Rule | Medium | 2 | 148 | 0.9865 |
| 2026-11-16 | peril_mismatch | Gen AI | High | 1 | 148 | 0.9932 |


## Issues found over the lookback window, by check

<details><summary>SQL</summary>

```sql
SELECT check_name, check_type, severity, count(*) issues FROM <catalog>.loss_ratio_coworker.dq_claims_issues GROUP BY ALL ORDER BY issues DESC
```
</details>

| check_name | check_type | severity | issues |
|---|---|---|---|
| pii_in_free_text | Gen AI | High | 86 |
| peril_mismatch | Gen AI | High | 23 |
| negative_amount | Rule | Medium | 10 |
| non_eur_currency | Rule | Medium | 9 |


## Gen AI findings with the ai_query explanation (descriptions are ai_mask'ed)

<details><summary>SQL</summary>

```sql
SELECT claim_id, report_date, check_name, cause_of_loss, ai_peril, loss_description_masked, ai_explanation FROM <catalog>.loss_ratio_coworker.dq_claims_issues
 WHERE check_type = 'Gen AI' ORDER BY report_date DESC, check_name LIMIT 12
```
</details>

| claim_id | report_date | check_name | cause_of_loss | ai_peril | loss_description_masked | ai_explanation |
|---|---|---|---|---|---|---|
| CLM-3077418 | 2026-11-16 | peril_mismatch | Theft | vehicle collision | Company car collided with a parked vehicle while reversing in Valencia | The issue is a mismatch between the coded cause of loss (Theft) and the peril inferred from the description (vehicle collision), indicating an incorrect classification. The claims handler should update the coded cause of |
| CLM-3077490 | 2026-11-16 | pii_in_free_text | Property Damage | third-party property damage | Our engineers damaged a client's server room flooring during installation in Bristol. Contact [MASKED] on [MASKED] or [MASKED] | The issue is that the description contains personal contact information, which is a data privacy concern. The claims handler should remove or mask the personal contact information from the description to fix the issue. |
| CLM-3077424 | 2026-11-16 | pii_in_free_text | Cargo Damage | water damage | Container of electronics arrived water-damaged at the port near Leeds. Contact [MASKED] on [MASKED] or [MASKED] | The issue is that the description contains personal contact information, which is a data quality problem. The claims handler should remove or mask the personal contact information from the description to fix the issue. |
| CLM-3077459 | 2026-11-16 | pii_in_free_text | Heavy Weather | heavy weather at sea | Heavy seas caused containers to shift and fall overboard en route to Vienna. Contact [MASKED] on [MASKED] or [MASKED] | The issue is that the description contains personal contact information, which is a data privacy concern. The claims handler should remove or mask the personal contact information from the description to fix the issue. |
| CLM-3077401 | 2026-11-16 | pii_in_free_text | Fire | fire | Electrical fire in the production hall in Toulouse; machinery and stock destroyed. Contact [MASKED] on [MASKED] or [MASKED] | The issue is that the description field contains personal contact information, which is a privacy concern. The claims handler should remove or mask the personal contact information ([MASKED] on [MASKED] or [MASKED]) from |
| CLM-3077258 | 2026-11-15 | peril_mismatch | Theft | hail | Severe hail shattered greenhouse panels and dented stock vehicles at the Stuttgart site | The issue is a mismatch between the coded cause of loss (Theft) and the peril inferred from the description (hail), which indicates the claim is actually related to hail damage, not theft. The claims handler should updat |
| CLM-3077226 | 2026-11-15 | peril_mismatch | Theft | hail | Severe hail shattered greenhouse panels and dented stock vehicles at the Vienna site | The issue is a mismatch between the coded cause of loss (Theft) and the peril inferred from the description (hail), indicating an incorrect classification. The claims handler should update the coded cause of loss to "Hai |
| CLM-3077353 | 2026-11-15 | peril_mismatch | Theft | vehicle collision | Company car collided with a parked vehicle while reversing in Lille | The issue is a mismatch between the coded cause of loss (Theft) and the peril inferred from the description (vehicle collision), indicating an incorrect classification. The claims handler should update the coded cause of |
| CLM-3077274 | 2026-11-15 | pii_in_free_text | Flood | flood | River flooding entered the ground floor of the Lille depot, water 40cm deep. Contact [MASKED] on [MASKED] or [MASKED] | The issue is that the description contains personal contact information, which is a privacy concern. The claims handler should remove or mask the personal contact information from the description to fix the issue. |
| CLM-3077360 | 2026-11-15 | pii_in_free_text | Hail | hail | Hailstones damaged roof tiles and skylights at the insured warehouse in Vienna. Contact [MASKED] on [MASKED] or [MASKED] | The issue is that the description contains personal contact information, which is a data quality problem. The claims handler should remove or mask the personal contact information from the description to fix the issue. |
| CLM-3077229 | 2026-11-15 | pii_in_free_text | Collision | vehicle collision | Company car collided with a parked vehicle while reversing in Zurich. Contact [MASKED] on [MASKED] or [MASKED] | The issue is that the description contains personal contact information, which is a data privacy concern. The claims handler should remove or mask the personal contact information from the description to fix the issue. |
| CLM-3077298 | 2026-11-15 | pii_in_free_text | Fire | fire | Kitchen fire spread to the dining area of the insured restaurant in Antwerp. Contact [MASKED] on [MASKED] or [MASKED] | The issue is that the description contains personal contact information, which is a privacy concern. The claims handler should remove or mask the personal contact information from the description to fix the issue. |


## Gen AI check accuracy against seeded defects (src/genai/04_evaluate_genai_dq.py)

<details><summary>SQL</summary>

```sql
SELECT check_name, genai_function, claims_checked, seeded_defects, flagged, true_positives, false_positives,
 false_negatives, precision, recall, f1 FROM <catalog>.loss_ratio_coworker.dq_genai_eval
 WHERE evaluated_at = (SELECT MAX(evaluated_at) FROM <catalog>.loss_ratio_coworker.dq_genai_eval)
```
</details>

| check_name | genai_function | claims_checked | seeded_defects | flagged | true_positives | false_positives | false_negatives | precision | recall | f1 |
|---|---|---|---|---|---|---|---|---|---|---|
| peril_mismatch | ai_classify | 1981 | 21 | 23 | 21 | 2 | 0 | 0.913 | 1.0 | 0.955 |
| pii_in_free_text | ai_mask | 1981 | 70 | 86 | 70 | 16 | 0 | 0.814 | 1.0 | 0.897 |


## ai_classify peril vs. recorded cause code (sample of mismatches)

<details><summary>SQL</summary>

```sql
SELECT claim_id, cause_of_loss, ai_peril, peril_consistent, pii_detected, loss_description_masked
 FROM <catalog>.loss_ratio_coworker.silver_claims_ai_checked WHERE NOT peril_consistent LIMIT 10
```
</details>

| claim_id | cause_of_loss | ai_peril | peril_consistent | pii_detected | loss_description_masked |
|---|---|---|---|---|---|
| CLM-3075754 | Theft | vehicle collision | false | false | Delivery van rear-ended at traffic lights in Nantes, bumper and tailgate damaged |
| CLM-3076076 | Theft | cargo theft | false | false | Thieves cut the fence at the Antwerp yard and removed copper cable |
| CLM-3076053 | Water Damage | fire | false | false | Kitchen fire spread to the dining area of the insured restaurant in Nantes |
| CLM-3075958 | Theft | vehicle collision | false | false | Delivery van rear-ended at traffic lights in Liège, bumper and tailgate damaged |
| CLM-3076151 | Theft | cargo theft | false | false | Thieves cut the fence at the Rotterdam yard and removed copper cable |
| CLM-3076160 | Theft | vehicle collision | false | false | Delivery van rear-ended at traffic lights in Zurich, bumper and tailgate damaged |
| CLM-3076450 | Theft | vehicle collision | false | false | Delivery van rear-ended at traffic lights in Valencia, bumper and tailgate damaged |
| CLM-3076477 | Theft | vehicle collision | false | false | Delivery van rear-ended at traffic lights in Stuttgart, bumper and tailgate damaged |
| CLM-3076234 | Professional Error | bodily injury | false | false | Visitor slipped on a wet floor at the Manchester premises and fractured a wrist |
| CLM-3076215 | Theft | vehicle collision | false |  |  |


## Row counts through the medallion

<details><summary>SQL</summary>

```sql
SELECT 'bronze_fnol' layer, count(*) rows FROM <catalog>.loss_ratio_coworker.bronze_fnol UNION ALL
 SELECT 'silver_claims', count(*) FROM <catalog>.loss_ratio_coworker.silver_claims UNION ALL
 SELECT 'silver_claims_ai_checked', count(*) FROM <catalog>.loss_ratio_coworker.silver_claims_ai_checked UNION ALL
 SELECT 'dq_claims_issues', count(*) FROM <catalog>.loss_ratio_coworker.dq_claims_issues UNION ALL
 SELECT 'bronze_premium', count(*) FROM <catalog>.loss_ratio_coworker.bronze_premium UNION ALL
 SELECT 'silver_premium', count(*) FROM <catalog>.loss_ratio_coworker.silver_premium UNION ALL
 SELECT 'gold_daily_loss_run_lf', count(*) FROM <catalog>.loss_ratio_coworker.gold_daily_loss_run_lf
```
</details>

| layer | rows |
|---|---|
| silver_claims | 3716 |
| silver_premium | 590 |
| bronze_fnol | 3750 |
| silver_claims_ai_checked | 1981 |
| dq_claims_issues | 128 |
| bronze_premium | 600 |
| gold_daily_loss_run_lf | 590 |


## Reconciliation: Lakeflow gold vs. original gold over the landed window

<details><summary>SQL</summary>

```sql
WITH lf AS (SELECT sum(incurred_loss) inc, sum(earned_premium) ep, min(as_of_date) d0, max(as_of_date) d1 FROM <catalog>.loss_ratio_coworker.gold_daily_loss_run_lf),
 og AS (SELECT sum(incurred_loss) inc, sum(earned_premium) ep FROM <catalog>.loss_ratio_coworker.gold_daily_loss_run, lf WHERE as_of_date BETWEEN lf.d0 AND lf.d1)
 SELECT lf.d0 from_date, lf.d1 to_date, round(lf.inc) lakeflow_incurred, round(og.inc) original_incurred,
 round(100 * (lf.inc - og.inc) / og.inc, 2) incurred_diff_pct,
 round(lf.inc / lf.ep, 4) lakeflow_loss_ratio, round(og.inc / og.ep, 4) original_loss_ratio FROM lf, og
```
</details>

| from_date | to_date | lakeflow_incurred | original_incurred | incurred_diff_pct | lakeflow_loss_ratio | original_loss_ratio |
|---|---|---|---|---|---|---|
| 2026-10-18 | 2026-11-16 | 1.39697699E8 | 1.44002524E8 | -2.99 | 0.6721 | 0.6712 |


## Rate adequacy per segment (Lakebase pricing + loss ratio vs target)

<details><summary>SQL</summary>

```sql
SELECT line_of_business, region, loss_ratio_30d, target_loss_ratio, lr_gap_pts, indicated_rate_change_pct,
 achieved_rate_change_pct, rate_shortfall_pts, quotes, bind_ratio, referral_ratio, proposed_rate_actions, adequacy_status
 FROM <catalog>.loss_ratio_coworker.gold_rate_adequacy ORDER BY rate_shortfall_pts DESC
```
</details>

| line_of_business | region | loss_ratio_30d | target_loss_ratio | lr_gap_pts | indicated_rate_change_pct | achieved_rate_change_pct | rate_shortfall_pts | quotes | bind_ratio | referral_ratio | proposed_rate_actions | adequacy_status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Property | DACH | 0.9706 | 0.6 | 37.1 | 61.8 | 2.9 | 58.9 | 307 | 0.397 | 0.117 | 0 | Rate inadequate: achieved rate change below indicated, no rate action |
| Liability | Southern Europe | 0.9402 | 0.66 | 28.0 | 42.4 | 2.0 | 40.4 | 342 | 0.368 | 0.073 | 0 | Rate inadequate: achieved rate change below indicated, no rate action |
| Marine | DACH | 0.6742 | 0.57 | 10.4 | 18.3 | 2.3 | 16.0 | 341 | 0.431 | 0.047 | 0 | Rate inadequate: achieved rate change below indicated, no rate action |
| Motor | UK & Ireland | 0.8344 | 0.7 | 13.4 | 19.2 | 4.2 | 15.0 | 307 | 0.427 | 0.085 | 1 | Rate action proposed: awaiting pricing decision |
| Marine | UK & Ireland | 0.6093 | 0.57 | 3.9 | 6.9 | 2.5 | 4.4 | 335 | 0.385 | 0.048 | 0 | Rate inadequate: achieved rate change below indicated, no rate action |
| Motor | Southern Europe | 0.7476 | 0.7 | 4.8 | 6.8 | 3.8 | 3.0 | 305 | 0.400 | 0.046 | 0 | Rate inadequate: achieved rate change below indicated, no rate action |
| Property | UK & Ireland | 0.6255 | 0.6 | 2.6 | 4.3 | 3.1 | 1.2 | 344 | 0.387 | 0.058 | 0 | Monitor: above target, achieved rate change covers the gap |
| Liability | DACH | 0.67 | 0.66 | 1.0 | 1.5 | 1.9 | -0.4 | 282 | 0.355 | 0.064 | 0 | Monitor: above target, achieved rate change covers the gap |
| Liability | UK & Ireland | 0.6663 | 0.66 | 0.6 | 0.9 | 2.0 | -1.1 | 308 | 0.364 | 0.032 | 0 | Monitor: above target, achieved rate change covers the gap |
| Motor | DACH | 0.7106 | 0.7 | 1.1 | 1.5 | 4.0 | -2.5 | 299 | 0.415 | 0.057 | 0 | Monitor: above target, achieved rate change covers the gap |
| Motor | Benelux | 0.6971 | 0.7 | -0.3 | -0.4 | 3.9 | -4.3 | 313 | 0.383 | 0.051 | 0 | Adequate |
| Property | Southern Europe | 0.5798 | 0.6 | -2.0 | -3.4 | 2.9 | -6.3 | 296 | 0.422 | 0.030 | 0 | Adequate |
| Motor | France | 0.6736 | 0.7 | -2.6 | -3.8 | 4.0 | -7.8 | 313 | 0.380 | 0.058 | 0 | Adequate |
| Property | France | 0.5561 | 0.6 | -4.4 | -7.3 | 3.1 | -10.4 | 306 | 0.422 | 0.039 | 0 | Adequate |
| Marine | France | 0.509 | 0.57 | -6.1 | -10.7 | 2.8 | -13.5 | 307 | 0.410 | 0.049 | 0 | Adequate |
| Liability | France | 0.5836 | 0.66 | -7.6 | -11.6 | 2.0 | -13.6 | 307 | 0.472 | 0.029 | 1 | Adequate |
| Liability | Benelux | 0.5692 | 0.66 | -9.1 | -13.8 | 2.0 | -15.8 | 278 | 0.388 | 0.065 | 0 | Adequate |
| Property | Benelux | 0.4865 | 0.6 | -11.3 | -18.9 | 3.1 | -22.0 | 304 | 0.431 | 0.059 | 0 | Adequate |
| Marine | Southern Europe | 0.4507 | 0.57 | -11.9 | -20.9 | 2.4 | -23.3 | 327 | 0.398 | 0.055 | 0 | Adequate |
| Marine | Benelux | 0.434 | 0.57 | -13.6 | -23.9 | 2.4 | -26.3 | 312 | 0.433 | 0.022 | 0 | Adequate |


## Today's watchlist (the alert the coworker raised)

<details><summary>SQL</summary>

```sql
SELECT line_of_business, region, status, primary_driver, round(lr_7d,3) lr_7d, round(lr_30d,3) lr_30d,
 round(target_loss_ratio,3) target, round(gap_7d_pts,1) gap_7d_pts FROM <catalog>.loss_ratio_coworker.v_loss_ratio_watchlist
 WHERE status <> 'GREEN' ORDER BY gap_7d_pts DESC
```
</details>

| line_of_business | region | status | primary_driver | lr_7d | lr_30d | target | gap_7d_pts |
|---|---|---|---|---|---|---|---|
| Property | DACH | RED | Catastrophe event | 2.659 | 0.981 | 0.6 | 205.9 |
| Liability | Southern Europe | RED | Large loss | 2.09 | 0.94 | 0.66 | 143.0 |
| Motor | UK & Ireland | RED | Frequency | 1.035 | 0.841 | 0.7 | 33.5 |
| Liability | UK & Ireland | AMBER | Within normal variation | 0.795 | 0.666 | 0.66 | 13.5 |
| Property | UK & Ireland | AMBER | Within normal variation | 0.728 | 0.593 | 0.6 | 12.8 |
| Liability | France | AMBER | Frequency | 0.768 | 0.584 | 0.66 | 10.8 |


## Team status of actions (snapshot of Lakebase ops.lr_actions)

<details><summary>SQL</summary>

```sql
SELECT team, status, count(*) actions FROM <catalog>.loss_ratio_coworker.lr_action_status GROUP BY ALL ORDER BY team, status
```
</details>

| team | status | actions |
|---|---|---|
| Claims | ACKNOWLEDGED | 1 |
| Claims | IN_PROGRESS | 1 |
| Claims | OPEN | 2 |
| Finance | OPEN | 1 |
| Pricing | OPEN | 2 |
| Reinsurance | OPEN | 2 |
| Reserving | OPEN | 1 |
| Underwriting | OPEN | 6 |


## Rate actions proposed to the pricing system (snapshot of Lakebase pricing.rate_actions)

<details><summary>SQL</summary>

```sql
SELECT rate_action_id, line_of_business, region, rate_change_pct, status, reason FROM <catalog>.loss_ratio_coworker.bronze_rate_actions
```
</details>

| rate_action_id | line_of_business | region | rate_change_pct | status | reason |
|---|---|---|---|---|---|
| RA-LR-20261116-MOT-UK | Motor | UK & Ireland | 7.5 | PROPOSED | RED on loss ratio, driver Frequency: Test whether the frequency trend is in the rating model and price a frequency load if it persists. |
| RA-LR-20261116-LIA-FRAN | Liability | France | 7.5 | PROPOSED | AMBER on loss ratio, driver Frequency: Test whether the frequency trend is in the rating model and price a frequency load if it persists. |
