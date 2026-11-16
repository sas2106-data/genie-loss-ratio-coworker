# 07 · Gen AI data-quality checks: precision, recall and LLM judge

Produced every run by [`src/genai/04_evaluate_genai_dq.py`](../../src/genai/04_evaluate_genai_dq.py) against the defects seeded by [`src/raw/03_land_raw_files.py`](../../src/raw/03_land_raw_files.py). The checks themselves are in [`src/pipeline/lrc_ingest_pipeline.sql`](../../src/pipeline/lrc_ingest_pipeline.sql) (`ai_classify`, `ai_mask`, `ai_query`).


## Precision / recall per check (latest run)

| check_name | genai_function | claims_checked | seeded_defects | flagged | true_positives | false_positives | false_negatives | precision | recall | f1 |
|---|---|---|---|---|---|---|---|---|---|---|
| peril_mismatch | ai_classify | 1981 | 21 | 23 | 21 | 2 | 0 | 0.913 | 1.0 | 0.955 |
| pii_in_free_text | ai_mask | 1981 | 70 | 86 | 70 | 16 | 0 | 0.814 | 1.0 | 0.897 |


## History across runs (tuning shows up here)

| run | check_name | precision | recall | f1 |
|---|---|---|---|---|
| 2026-11-16 03:57 | peril_mismatch | 0.447 | 1.0 | 0.618 |
| 2026-11-16 03:57 | pii_in_free_text | 0.805 | 1.0 | 0.892 |
| 2026-11-16 04:55 | peril_mismatch | 0.955 | 1.0 | 0.977 |
| 2026-11-16 04:55 | pii_in_free_text | 0.778 | 1.0 | 0.875 |
| 2026-11-16 05:20 | peril_mismatch | 0.913 | 1.0 | 0.955 |
| 2026-11-16 05:20 | pii_in_free_text | 0.814 | 1.0 | 0.897 |


## LLM judge of the ai_query explanations (independent model family)

| judge_endpoint | check_name | judged | correct_check | actionable | no_personal_data | faithful | avg_score |
|---|---|---|---|---|---|---|---|
| databricks-claude-sonnet-5-5 | negative_amount | 2 | 1.0 | 1.0 | 1.0 | 0.5 | 3.0 |
| databricks-claude-sonnet-5-5 | non_eur_currency | 4 | 1.0 | 1.0 | 1.0 | 0.25 | 2.5 |
| databricks-claude-sonnet-5-5 | peril_mismatch | 6 | 1.0 | 1.0 | 1.0 | 1.0 | 4.8 |
| databricks-claude-sonnet-5-5 | pii_in_free_text | 28 | 0.857 | 1.0 | 1.0 | 0.893 | 3.46 |
|  |  | 40 | 0.897 | 1.0 | 1.0 | 0.821 | 3.51 |
| databricks-claude-sonnet-5-5 |  | 40 | 0.897 | 1.0 | 1.0 | 0.821 | 3.51 |


## Lowest-scored explanations (what the judge objected to)

| check_name | score | reason | ai_explanation |
|---|---|---|---|
| peril_mismatch |  |  |  |
| non_eur_currency | 2 | Addresses the currency check, but the amount 7450.0 is not in the inputs, and the fix is vague (convert or relabel?). | The issue is that the incurred amount of 7450.0 is not in Euros, as required. The claims handler should update the incurred amount to the correct currency, presumably Euros, to resolve the non_eur_currency check failure. |
| non_eur_currency | 2 | Names the non-EUR check, but Zurich is in Switzerland (CHF), so 'match location' is wrong; the amount and currency are not in the inputs. | The issue is that the incurred amount (41,225.0) is not in Euros, despite the location being Zurich, which suggests a European currency. The claims handler should update the currency of the incurred amount to Euros (EUR) |
| pii_in_free_text | 2 | Explains a cause-code mismatch rather than the failed pii_in_free_text check; ignores masked contact details in the description. | The issue is that the coded cause of loss is "Cargo Damage" but the description suggests "water damage", indicating a potential inconsistency. The claims handler should update the coded cause of loss to "Water Damage" to |
| pii_in_free_text | 2 | Flags 'Vienna' as PII and ignores the masked contact details, which are the real PII; the fix is misdirected. | The issue is that the description contains location information ("Vienna") which may be considered personal identifiable information (PII). The claims handler should remove or mask the location to fix the issue and ensur |
| pii_in_free_text | 2 | Blames the city Stuttgart as PII, ignoring the masked personal identifier; advice is misdirected and the claim is speculative. | The issue is that the description field contains location-specific information (Stuttgart) which may be considered personal or sensitive data. The claims handler should remove or mask the location (Stuttgart) from the de |
