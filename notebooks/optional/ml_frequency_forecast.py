# Databricks notebook source
# MAGIC %md
# MAGIC # Optional · ML: claim-frequency forecast, registered in Unity Catalog, joined with Lakebase team status
# MAGIC
# MAGIC **Optional module: the main flow does not need it.** Run it after step 04 (after step 12 for the escalations).
# MAGIC
# MAGIC The watchlist is rules (is the loss ratio above threshold?) plus Genie (why?). This adds a **trained model**
# MAGIC that asks the forward-looking question: *will claim frequency keep rising next week?*
# MAGIC
# MAGIC | Step | What |
# MAGIC |---|---|
# MAGIC | Features | per line × region and week: claim counts and frequency (claims per EUR 1m earned) over the last 1, 2, 4 and 13 weeks, earned premium, seasonality |
# MAGIC | Target | claim count in the **next 7 days** |
# MAGIC | Model | gradient-boosted trees (scikit-learn), time-based split (last 8 weeks held out) |
# MAGIC | Baseline | naive: next week = last week. The model must beat it to be promoted |
# MAGIC | Registry | MLflow → Unity Catalog model `lrc_frequency_forecast`, alias `champion` |
# MAGIC | Output | `lr_frequency_forecast` per segment, and `lr_forecast_escalations`: rising forecast **and** the team action in Lakebase still OPEN |

# COMMAND ----------

# MAGIC %pip install -q "mlflow>=2.16" "scikit-learn>=1.4"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ../00_setup

# COMMAND ----------

FQ = f"`{CATALOG}`.`{SCHEMA}`"
MODEL = f"{CATALOG}.{SCHEMA}.lrc_frequency_forecast"

# COMMAND ----------

# MAGIC %md ## 1 · Weekly features from the governed loss run

# COMMAND ----------

import numpy as np
import pandas as pd

daily = spark.sql(f"""
  SELECT as_of_date, line_of_business, region, SUM(claim_count) claims, SUM(earned_premium) premium
  FROM {FQ}.gold_daily_loss_run GROUP BY ALL""").toPandas()
daily["as_of_date"] = pd.to_datetime(daily["as_of_date"])
daily = daily.sort_values(["line_of_business", "region", "as_of_date"])

rows = []
for (lob, reg), g in daily.groupby(["line_of_business", "region"]):
    g = g.set_index("as_of_date").asfreq("D", fill_value=0)
    c, p = g["claims"].astype(float), g["premium"].astype(float)
    f = pd.DataFrame({
        "c7": c.rolling(7).sum(), "c14": c.rolling(14).sum(), "c28": c.rolling(28).sum(), "c91": c.rolling(91).sum(),
        "p7": p.rolling(7).sum(), "p28": p.rolling(28).sum(),
    })
    f["freq7"] = f.c7 / (f.p7 / 1e6)
    f["freq28"] = f.c28 / (f.p28 / 1e6)
    f["trend_7_vs_28"] = f.c7 / (f.c28 / 4).replace(0, np.nan)
    f["woy_sin"] = np.sin(2 * np.pi * f.index.isocalendar().week.astype(int) / 52)
    f["woy_cos"] = np.cos(2 * np.pi * f.index.isocalendar().week.astype(int) / 52)
    f["target_next7"] = c[::-1].rolling(7).sum()[::-1].shift(-1)      # claims in the next 7 days
    f["line_of_business"], f["region"] = lob, reg
    rows.append(f.iloc[::7])                                            # one row per week
data = pd.concat(rows).reset_index().rename(columns={"index": "as_of_date"})
data = data.dropna(subset=["c91", "trend_7_vs_28"])
seg = pd.get_dummies(data[["line_of_business", "region"]], dtype=float)
FEATURES = ["c7", "c14", "c28", "c91", "p7", "p28", "freq7", "freq28", "trend_7_vs_28", "woy_sin", "woy_cos"] + list(seg.columns)
X_all = pd.concat([data[FEATURES[:11]], seg], axis=1)
print(f"{len(data):,} weekly rows · {data[['line_of_business','region']].drop_duplicates().shape[0]} segments · {len(FEATURES)} features")

# COMMAND ----------

# MAGIC %md ## 2 · Train with a time-based hold-out and compare with the naive baseline

# COMMAND ----------

import mlflow
from mlflow.models import infer_signature
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

labelled = data["target_next7"].notna()
cutoff = data.loc[labelled, "as_of_date"].max() - pd.Timedelta(weeks=8)
train = labelled & (data.as_of_date <= cutoff)
test = labelled & (data.as_of_date > cutoff)
X_tr, y_tr, X_te, y_te = X_all[train], data.loc[train, "target_next7"], X_all[test], data.loc[test, "target_next7"]

mlflow.set_registry_uri("databricks-uc")
me = spark.sql("SELECT current_user()").first()[0]
mlflow.set_experiment(f"/Users/{me}/lrc_frequency_forecast")
with mlflow.start_run(run_name="hgb_next7_claims") as run:
    model = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, random_state=7)
    model.fit(X_tr, y_tr)
    pred = model.predict(X_te)
    mae_model = mean_absolute_error(y_te, pred)
    mae_naive = mean_absolute_error(y_te, X_te["c7"])
    improvement = 1 - mae_model / mae_naive
    mlflow.log_params({"model": "HistGradientBoostingRegressor", "max_iter": 300, "learning_rate": 0.05, "holdout_weeks": 8})
    mlflow.log_metrics({"mae_model": mae_model, "mae_naive": mae_naive, "improvement_vs_naive": improvement,
                        "train_rows": len(X_tr), "test_rows": len(X_te)})
    info = mlflow.sklearn.log_model(model, "model", signature=infer_signature(X_tr, model.predict(X_tr.head(5))),
                                    input_example=X_tr.head(3), registered_model_name=MODEL)
print(f"hold-out MAE: model {mae_model:.2f} vs naive {mae_naive:.2f} claims/week → {improvement:+.1%} better than naive")

# COMMAND ----------

# MAGIC %md ## 3 · Promote only if it beats the baseline

# COMMAND ----------

from mlflow import MlflowClient
client = MlflowClient(registry_uri="databricks-uc")
version = max(int(v.version) for v in client.search_model_versions(f"name='{MODEL}'"))
if improvement > 0:
    client.set_registered_model_alias(MODEL, "champion", version)
    print(f"{MODEL} v{version} → alias champion")
else:
    print(f"{MODEL} v{version} not promoted: it does not beat the naive baseline")

# COMMAND ----------

# MAGIC %md ## 4 · Score the latest week with the champion and combine with Lakebase team status

# COMMAND ----------

try:
    champion = mlflow.sklearn.load_model(f"models:/{MODEL}@champion")
except Exception:  # first run and the model did not beat naive: score with this run's version
    champion = mlflow.sklearn.load_model(f"models:/{MODEL}/{version}")
latest = data.groupby(["line_of_business", "region"]).tail(1)
Xl = X_all.loc[latest.index]
out = latest[["as_of_date", "line_of_business", "region", "c7", "c28"]].copy()
out["forecast_next7_claims"] = np.round(champion.predict(Xl), 1)
out["weekly_avg_last4"] = out.c28 / 4
out["forecast_vs_4wk_avg_pct"] = np.round(100 * (out.forecast_next7_claims / out.weekly_avg_last4 - 1), 1)
out["frequency_outlook"] = np.where(out.forecast_vs_4wk_avg_pct > 15, "RISING", np.where(out.forecast_vs_4wk_avg_pct < -15, "FALLING", "STABLE"))
out["model_version"] = int(version)
out = out.rename(columns={"c7": "claims_last7"}).drop(columns=["c28"])
spark.createDataFrame(out).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{FQ}.lr_frequency_forecast")
spark.sql(f"COMMENT ON TABLE {FQ}.lr_frequency_forecast IS 'Next-7-day claim-count forecast per segment from UC model lrc_frequency_forecast@champion.'")
display(spark.table(f"{FQ}.lr_frequency_forecast").orderBy("forecast_vs_4wk_avg_pct", ascending=False))

# COMMAND ----------

# MAGIC %md
# MAGIC **Escalation rule:** the model expects frequency to keep rising **and** the owning team's action in Lakebase
# MAGIC (`lr_action_status`, snapshotted from `ops.lr_actions`) is still OPEN. That is the list a CUO wants on Monday.

# COMMAND ----------

if not spark.catalog.tableExists(f"{CATALOG}.{SCHEMA}.lr_action_status"):
    dbutils.notebook.exit("Forecast written. Run steps 09-12 first to join it with the team status in Lakebase.")

esc = spark.sql(f"""
SELECT f.line_of_business, f.region, f.claims_last7, f.forecast_next7_claims, f.forecast_vs_4wk_avg_pct,
       a.team, a.priority, a.status AS lakebase_status, a.action
FROM {FQ}.lr_frequency_forecast f
JOIN {FQ}.lr_action_status a USING (line_of_business, region)
WHERE f.frequency_outlook = 'RISING' AND a.status = 'OPEN'
""")
esc.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{FQ}.lr_forecast_escalations")
spark.sql(f"COMMENT ON TABLE {FQ}.lr_forecast_escalations IS 'Segments where the frequency forecast is rising and the Lakebase team action is still OPEN.'")
display(esc)
