# 07 · Gen AI data-quality checks: precision, recall and LLM judge

Produced every run by [`src/genai/04_evaluate_genai_dq.py`](../../src/genai/04_evaluate_genai_dq.py) against the defects seeded by [`src/raw/03_land_raw_files.py`](../../src/raw/03_land_raw_files.py). The checks themselves are in [`src/pipeline/lrc_ingest_pipeline.sql`](../../src/pipeline/lrc_ingest_pipeline.sql) (`ai_classify`, `ai_mask`, `ai_query`).


## Precision / recall per check (latest run)

| check_name | genai_function | claims_checked | seeded_defects | flagged | true_positives | false_positives | false_negatives | precision | recall | f1 |
|---|---|---|---|---|---|---|---|---|---|---|
| peril_mismatch | ai_classify | 1981 | 21 | 22 | 21 | 1 | 0 | 0.955 | 1.0 | 0.977 |
| pii_in_free_text | ai_mask | 1981 | 70 | 89 | 70 | 19 | 0 | 0.787 | 1.0 | 0.881 |


## History across runs (tuning shows up here)

| run | check_name | precision | recall | f1 |
|---|---|---|---|---|
| 2026-11-16 03:57 | peril_mismatch | 0.447 | 1.0 | 0.618 |
| 2026-11-16 03:57 | pii_in_free_text | 0.805 | 1.0 | 0.892 |
| 2026-11-16 04:55 | peril_mismatch | 0.955 | 1.0 | 0.977 |
| 2026-11-16 04:55 | pii_in_free_text | 0.778 | 1.0 | 0.875 |
| 2026-11-16 05:20 | peril_mismatch | 0.913 | 1.0 | 0.955 |
| 2026-11-16 05:20 | pii_in_free_text | 0.814 | 1.0 | 0.897 |
| 2026-11-16 06:07 | peril_mismatch | 0.955 | 1.0 | 0.977 |
| 2026-11-16 06:07 | pii_in_free_text | 0.787 | 1.0 | 0.881 |


## LLM judge of the ai_query explanations (independent model family)

| judge_endpoint | check_name | judged | correct_check | actionable | no_personal_data | faithful | avg_score |
|---|---|---|---|---|---|---|---|
| databricks-claude-sonnet-5-5 | negative_amount | 2 | 1.0 | 1.0 | 1.0 | 0.0 | 3.0 |
| databricks-claude-sonnet-5-5 | non_eur_currency | 4 | 1.0 | 1.0 | 1.0 | 0.0 | 2.5 |
| databricks-claude-sonnet-5-5 | peril_mismatch | 6 | 1.0 | 1.0 | 1.0 | 1.0 | 4.83 |
| databricks-claude-sonnet-5-5 | pii_in_free_text | 28 | 0.75 | 0.964 | 1.0 | 0.821 | 3.21 |
|  |  | 40 | 0.825 | 0.975 | 1.0 | 0.725 | 3.38 |
| databricks-claude-sonnet-5-5 |  | 40 | 0.825 | 0.975 | 1.0 | 0.725 | 3.38 |


## Lowest-scored explanations (what the judge objected to)

| check_name | score | reason | ai_explanation |
|---|---|---|---|
| pii_in_free_text | 1 | Explains a cause mismatch, not the failed pii_in_free_text check; never mentions masked contact details in the description. | The issue is that the coded cause of loss is "Cargo Damage" but the description suggests "water damage", indicating a potential inconsistency. The claims handler should update the coded cause of loss to "Water Damage" to |
| non_eur_currency | 2 | Addresses non_eur_currency and suggests converting to EUR, but the 7450.0 incurred amount appears nowhere in the provided inputs, so it is invented. | The issue is that the incurred amount of 7450.0 is not in Euros, as indicated by the check failed: non_eur_currency error. The claims handler should update the incurred amount to the equivalent value in Euros to resolve  |
| non_eur_currency | 2 | Flags non-EUR currency, but the amount 41225.0 isn't in the inputs, and the 'despite Zurich' logic and CHF guess are speculative and confused. | The issue is that the incurred amount of 41225.0 is not in Euros, despite the location being Zurich, which suggests a potential currency mismatch. The claims handler should verify and update the currency of the incurred  |
| pii_in_free_text | 2 | Explains a cause-of-loss mismatch, not the failed pii_in_free_text check; ignores masked contact details in the description. | The issue is that the coded cause of loss is "Cargo Damage" but the description suggests "water damage", indicating a potential inconsistency. The claims handler should update the coded cause of loss to "Water Damage" to |
| pii_in_free_text | 2 | Addresses PII check and gives a fix, but claims PII was not fully masked, while the description shows only [MASKED] placeholders. | The issue is that the description contains personally identifiable information (PII) which was not fully masked. The claims handler should re-mask the description to completely remove any PII, such as names and contact i |
| pii_in_free_text | 2 | Blames the generic 'Vienna premises' location; the masked token suggests a name was the PII. Advice is actionable but the cause is speculative. | The issue is that the description contains a location ("Vienna premises") which may be considered personal or sensitive information. The claims handler should mask or remove the location from the description to protect s |
