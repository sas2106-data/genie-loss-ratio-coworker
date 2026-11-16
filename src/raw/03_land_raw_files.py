# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Land synthetic source files in a raw volume
# MAGIC
# MAGIC Simulates the source systems of a commercial P&C insurer dropping files into a **Unity Catalog volume**, so the
# MAGIC Lakeflow pipeline (`src/pipeline/lrc_ingest_pipeline.sql`) can ingest them incrementally with Auto Loader.
# MAGIC
# MAGIC | Folder in `/Volumes/<catalog>/<schema>/raw/` | Format | What it is |
# MAGIC |---|---|---|
# MAGIC | `claims_fnol/report_date=YYYY-MM-DD/` | JSON lines | First notice of loss: claim header, amounts and a **free-text loss description** |
# MAGIC | `premium_bordereaux/as_of=YYYY-MM-DD/` | CSV | Earned premium per line of business × region × day, as a broker bordereau |
# MAGIC
# MAGIC The files are drawn from the synthetic book built by `01_generate_loss_run.py`, so the pipeline's gold table
# MAGIC reconciles with `gold_daily_loss_run`. A small share of records carry **deliberate data-quality defects**
# MAGIC for the rule-based and Gen AI checks to find:
# MAGIC
# MAGIC | Defect | Rate | Caught by |
# MAGIC |---|---|---|
# MAGIC | Cause-of-loss code contradicts the description (e.g. hail damage coded as Theft) | ~2% | `ai_classify` |
# MAGIC | Personal data in the description (name, phone, email) | ~3% | `ai_mask` |
# MAGIC | Negative incurred amount | ~0.3% | expectation |
# MAGIC | Report date in the future / loss date after report date | ~0.3% | expectation |
# MAGIC | Duplicate claim resent in a later file | ~1% | de-duplication |
# MAGIC | Non-EUR currency without conversion | ~0.5% | expectation |
# MAGIC
# MAGIC All data is synthetic. Re-running for the same dates overwrites those dates' files.

# COMMAND ----------

dbutils.widgets.text("catalog", "")
dbutils.widgets.text("schema", "loss_ratio_coworker")
dbutils.widgets.text("days", "30")          # how many report dates to land (backfill), ending today
dbutils.widgets.text("files_per_day", "2")  # simulate several drops per day
CATALOG = dbutils.widgets.get("catalog") or spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = dbutils.widgets.get("schema")
DAYS = int(dbutils.widgets.get("days"))
FILES_PER_DAY = int(dbutils.widgets.get("files_per_day"))

spark.sql(f"CREATE VOLUME IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`.raw COMMENT 'Raw landing zone for synthetic source files (FNOL claims JSON, premium bordereaux CSV)'")
RAW = f"/Volumes/{CATALOG}/{SCHEMA}/raw"
print(f"Landing into {RAW}")

# COMMAND ----------

import json, os, random
from datetime import timedelta
import numpy as np
import pandas as pd

rng = np.random.default_rng(7)
random.seed(7)

claims = spark.table(f"`{CATALOG}`.`{SCHEMA}`.claims").toPandas()
premium = spark.table(f"`{CATALOG}`.`{SCHEMA}`.earned_premium_daily").toPandas()
claims["report_date"] = pd.to_datetime(claims.report_date).dt.date
claims["loss_date"] = pd.to_datetime(claims.loss_date).dt.date
premium["as_of_date"] = pd.to_datetime(premium.as_of_date).dt.date
last = max(claims.report_date.max(), premium.as_of_date.max())
dates = [last - timedelta(days=i) for i in range(DAYS)][::-1]

# COMMAND ----------

# MAGIC %md ## Free-text loss descriptions (what an FNOL handler or broker types)

# COMMAND ----------

CITY = {"UK & Ireland": ["Manchester", "Dublin", "Leeds", "Bristol"], "France": ["Lyon", "Lille", "Toulouse", "Nantes"],
        "DACH": ["Munich", "Stuttgart", "Zurich", "Vienna"], "Southern Europe": ["Milan", "Madrid", "Porto", "Valencia"],
        "Benelux": ["Antwerp", "Rotterdam", "Utrecht", "Liège"]}
TEXT = {
    "Hail": ["Hailstones damaged roof tiles and skylights at the insured warehouse in {c}",
             "Severe hail shattered greenhouse panels and dented stock vehicles at the {c} site"],
    "Fire": ["Electrical fire in the production hall in {c}; machinery and stock destroyed", "Kitchen fire spread to the dining area of the insured restaurant in {c}"],
    "Flood": ["River flooding entered the ground floor of the {c} depot, water 40cm deep", "Flash flood after heavy rain damaged inventory stored at basement level in {c}"],
    "Storm/Wind": ["Storm winds lifted part of the roof membrane at the {c} distribution centre", "Fallen tree after windstorm damaged the office facade in {c}"],
    "Water Damage": ["Burst pipe on the third floor caused water damage to offices below in {c}", "Leaking sprinkler head soaked packaged goods in the {c} warehouse"],
    "Theft": ["Break-in overnight at the {c} store; electronics stolen from the stockroom", "Thieves cut the fence at the {c} yard and removed copper cable"],
    "Collision": ["Delivery van rear-ended at traffic lights in {c}, bumper and tailgate damaged", "Company car collided with a parked vehicle while reversing in {c}"],
    "Third-Party PD": ["Insured truck scraped a third party's gate while turning in {c}", "Our vehicle damaged a third-party bus shelter in {c}"],
    "Third-Party BI": ["Pedestrian injured when our delivery vehicle mounted the kerb in {c}", "Cyclist reports neck injury after collision with fleet car in {c}"],
    "Weather": ["Fleet vehicle damaged by falling branches during a storm in {c}", "Car parked outdoors in {c} damaged by large hailstones"],
    "Bodily Injury": ["Visitor slipped on a wet floor at the {c} premises and fractured a wrist", "Contractor fell from a ladder on our {c} site, serious back injury"],
    "Property Damage": ["Our engineers damaged a client's server room flooring during installation in {c}", "Crane load dropped onto a neighbouring roof in {c}"],
    "Professional Error": ["Client alleges design error in our structural drawings for a {c} project", "Incorrect advice in a compliance report led to a client fine in {c}"],
    "Product Liability": ["Customer claims our heating unit overheated and damaged their {c} shop", "Defective component in supplied machinery caused a stoppage at a {c} plant"],
    "Cargo Damage": ["Container of electronics arrived water-damaged at the port near {c}", "Pallets crushed during loading, consignment for {c} rejected"],
    "Cargo Theft": ["Trailer with pharmaceutical cargo stolen from a rest area near {c}", "Container seal broken, part of the cargo missing on arrival in {c}"],
    "Vessel Collision": ["Feeder vessel struck the quay while berthing near {c}", "Barge collided with a lock gate on the waterway near {c}"],
    "Heavy Weather": ["Heavy seas caused containers to shift and fall overboard en route to {c}", "Storm at sea damaged deck cargo bound for {c}"],
}
WRONG = {"Hail": "Theft", "Flood": "Fire", "Collision": "Theft", "Bodily Injury": "Professional Error", "Cargo Theft": "Heavy Weather",
         "Fire": "Water Damage", "Theft": "Storm/Wind"}
NAMES = ["Anna Becker", "Luca Rossi", "Sophie Martin", "James O'Brien", "Eva de Vries", "Carlos Ruiz"]

def describe(cause, region):
    return random.choice(TEXT.get(cause, ["Loss reported at the insured location in {c}"])).format(c=random.choice(CITY[region]))

# COMMAND ----------

# MAGIC %md ## Write the files

# COMMAND ----------

def clean_dir(path):
    try:
        for f in dbutils.fs.ls(path):
            dbutils.fs.rm(f.path, True)
    except Exception:
        pass

stats = {"claims": 0, "premium_rows": 0, "mismatch": 0, "pii": 0, "neg": 0, "dates": 0, "dupes": 0, "ccy": 0}
resend = []  # duplicates resent in the next day's file
for d in dates:
    day = claims[claims.report_date == d].copy()
    recs = []
    for r in day.itertuples(index=False):
        cause = r.cause_of_loss
        rec = {"claim_id": r.claim_id, "policy_id": r.policy_id, "line_of_business": r.line_of_business, "region": r.region,
               "loss_date": str(r.loss_date), "report_date": str(r.report_date), "cause_of_loss": cause,
               "incurred_loss": round(float(r.incurred_loss), 2), "paid_loss": round(float(r.paid_loss), 2),
               "case_reserve": round(float(r.case_reserve), 2), "currency": "EUR", "event_tag": r.event_tag,
               "loss_description": describe(cause, r.region), "source_system": random.choice(["ClaimsHub", "BrokerPortal", "FNOL-App"])}
        u = rng.random()
        if u < 0.02 and cause in WRONG:                       # code contradicts the narrative
            rec["cause_of_loss"] = WRONG[cause]; stats["mismatch"] += 1
        elif u < 0.05:                                        # personal data typed into free text
            n = random.choice(NAMES)
            rec["loss_description"] += f". Contact {n} on +44 7700 {rng.integers(100000, 999999)} or {n.split()[0].lower()}@example.com"
            stats["pii"] += 1
        elif u < 0.053:
            rec["incurred_loss"] = -abs(rec["incurred_loss"]); stats["neg"] += 1
        elif u < 0.056:
            rec["report_date"] = str(d + timedelta(days=int(rng.integers(3, 30)))); stats["dates"] += 1
        elif u < 0.061:
            rec["currency"] = "GBP"; stats["ccy"] += 1
        if rng.random() < 0.01:
            resend.append(dict(rec)); stats["dupes"] += 1
        recs.append(rec)
    if resend and d != dates[0]:
        recs += resend; resend = []
    random.shuffle(recs)
    path = f"{RAW}/claims_fnol/report_date={d}"
    clean_dir(path); os.makedirs(path, exist_ok=True)
    for b, chunk in enumerate(np.array_split(np.arange(len(recs)), FILES_PER_DAY)):
        with open(f"{path}/fnol_{d:%Y%m%d}_{b + 1:02d}.json", "w") as fh:
            for i in chunk:
                fh.write(json.dumps(recs[i]) + "\n")
    stats["claims"] += len(recs)

    p = premium[premium.as_of_date == d].copy()
    p["currency"] = "EUR"; p["bordereau_id"] = [f"BDX-{d:%Y%m%d}-{i:03d}" for i in range(len(p))]
    if len(p) and rng.random() < 0.2:                       # occasional sign error from a broker
        p.loc[p.index[0], "earned_premium"] *= -1
    ppath = f"{RAW}/premium_bordereaux/as_of={d}"
    clean_dir(ppath); os.makedirs(ppath, exist_ok=True)
    p[["bordereau_id", "as_of_date", "line_of_business", "region", "earned_premium", "currency"]].to_csv(
        f"{ppath}/premium_{d:%Y%m%d}.csv", index=False)
    stats["premium_rows"] += len(p)

print(f"Landed {len(dates)} days ({dates[0]} → {dates[-1]}) into {RAW}")
print(json.dumps(stats, indent=1))
