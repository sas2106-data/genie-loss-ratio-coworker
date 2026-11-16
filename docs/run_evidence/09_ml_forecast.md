# 09 · ML: claim-frequency forecast registered in Unity Catalog

Trained by [`src/ml/06_train_frequency_forecast.py`](../../src/ml/06_train_frequency_forecast.py): gradient-boosted trees on weekly features from `gold_daily_loss_run`, time-based hold-out, compared with a naive baseline, registered as `<catalog>.loss_ratio_coworker.lrc_frequency_forecast` with alias `champion`. Training metrics are printed in [`notebooks/`](notebooks/) (task `train_frequency_forecast`).


## Registered model

| model | aliases | owner |
|---|---|---|
| <catalog>.loss_ratio_coworker.lrc_frequency_forecast | champion→v3 | <user> |


## Forecast per segment (latest week)

| line_of_business | region | claims_last7 | forecast_next7_claims | weekly_avg_last4 | forecast_vs_4wk_avg_pct | frequency_outlook | model_version |
|---|---|---|---|---|---|---|---|
| Marine | Benelux | 8.0 | 10.8 | 8.3 | 30.9 | RISING | 3 |
| Liability | UK & Ireland | 26.0 | 29.7 | 24.3 | 22.5 | RISING | 3 |
| Property | Southern Europe | 24.0 | 37.1 | 32.0 | 15.9 | RISING | 3 |
| Marine | France | 16.0 | 18.6 | 16.3 | 14.5 | STABLE | 3 |
| Marine | Southern Europe | 12.0 | 15.6 | 14.0 | 11.4 | STABLE | 3 |
| Marine | DACH | 23.0 | 22.3 | 21.0 | 6.2 | STABLE | 3 |
| Property | UK & Ireland | 46.0 | 48.4 | 46.8 | 3.5 | STABLE | 3 |
| Liability | Benelux | 20.0 | 13.9 | 13.5 | 3.0 | STABLE | 3 |
| Motor | France | 85.0 | 85.1 | 83.0 | 2.5 | STABLE | 3 |
| Motor | Benelux | 56.0 | 53.3 | 52.3 | 2.0 | STABLE | 3 |
| Property | France | 39.0 | 38.2 | 38.3 | -0.1 | STABLE | 3 |
| Property | Benelux | 22.0 | 23.1 | 23.5 | -1.7 | STABLE | 3 |
| Motor | Southern Europe | 87.0 | 75.8 | 78.8 | -3.7 | STABLE | 3 |
| Motor | DACH | 98.0 | 92.1 | 96.0 | -4.1 | STABLE | 3 |
| Liability | Southern Europe | 17.0 | 20.1 | 21.0 | -4.3 | STABLE | 3 |
| Property | DACH | 81.0 | 47.9 | 50.3 | -4.7 | STABLE | 3 |
| Liability | DACH | 27.0 | 24.9 | 26.8 | -6.9 | STABLE | 3 |
| Liability | France | 19.0 | 21.6 | 23.8 | -9.1 | STABLE | 3 |
| Marine | UK & Ireland | 21.0 | 21.5 | 25.0 | -14.0 | STABLE | 3 |
| Motor | UK & Ireland | 149.0 | 109.1 | 127.3 | -14.3 | STABLE | 3 |


## Escalations: forecast RISING and the Lakebase action still OPEN

| line_of_business | region | forecast_vs_4wk_avg_pct | team | priority | lakebase_status | action |
|---|---|---|---|---|---|---|
| Liability | UK & Ireland | 22.5 | Underwriting | P2 | OPEN | Monitor. No action unless the 30-day loss ratio also breaches. |
