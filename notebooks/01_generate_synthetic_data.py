# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Generate synthetic source data and land it in the raw volume
# MAGIC
# MAGIC Simulates the source systems of a European commercial P&C insurer (4 lines of business, 5 regions) and drops their
# MAGIC files into the Unity Catalog volume `raw`, the way an FNOL system and brokers would. Nothing is written to tables yet:
# MAGIC the Lakeflow pipeline (steps 02 to 04) ingests these files. All data is synthetic, with a fixed seed.
# MAGIC
# MAGIC | Folder in `/Volumes/<catalog>/<schema>/raw/` | Format | What it is |
# MAGIC |---|---|---|
# MAGIC | `claims_fnol/<YYYY-MM>/` and `claims_fnol/<YYYY-MM-DD>/` | JSON lines | first notice of loss: claim, amounts, status and a free-text description |
# MAGIC | `premium_bordereaux/<YYYY-MM>/` and `premium_bordereaux/<YYYY-MM-DD>/` | CSV | earned premium per line of business, region and day |
# MAGIC
# MAGIC Only this year's claims and premium are landed (from 1 January, or the last 180 days if that is longer), which keeps the
# MAGIC tutorial small (about 38,000 claims) while the year-to-date and 90-day baselines stay complete. History is landed as one
# MAGIC file per month, and the last 30 days as daily drops, so the pipeline sees both a backfill and a daily feed. Three **planted events** give the coworker something real to find:
# MAGIC 1. **Hailstorm, DACH Property** (loss dates in the last 6 days): a burst of high-severity claims.
# MAGIC 2. **Frequency creep, UK & Ireland Motor** (last 21 days): about 45% more collisions at normal severity.
# MAGIC 3. **Large bodily-injury loss, Southern Europe Liability** (reported 3 days ago): one EUR 2.4m claim.
# MAGIC
# MAGIC A small share of records carry **planted data-quality defects** for step 03 to find: a cause-of-loss code that
# MAGIC contradicts the description (~2%), personal data in the free text (~3%), negative amounts, report dates in the future,
# MAGIC non-EUR currency and duplicates resent in a later file.

# COMMAND ----------

# MAGIC %run ./00_setup

# COMMAND ----------

# MAGIC %md
# MAGIC ## The synthetic book: policies, earned premium and claims

# COMMAND ----------

import numpy as np
import pandas as pd
from datetime import date, timedelta

SEED = 42
rng = np.random.default_rng(SEED)

TODAY = np.datetime64(date.today())
START = np.datetime64("2025-01-01")
DAYS = pd.date_range(str(START), str(TODAY), freq="D")
N_DAYS = len(DAYS)

LOBS = ["Property", "Motor", "Liability", "Marine"]
LOB_W = np.array([34, 30, 24, 12], float)
REGIONS = ["UK & Ireland", "France", "DACH", "Southern Europe", "Benelux"]
REG_W = np.array([26, 20, 24, 18, 12], float)
BROKERS = ["Broker A", "Broker B", "Broker C", "Broker D", "Direct"]

PREM_MU = {"Property": 10.6, "Motor": 10.2, "Liability": 10.4, "Marine": 10.9}
FREQ = {"Property": 0.55, "Motor": 1.35, "Liability": 0.45, "Marine": 0.75}       # claims / policy-year
SEV_MU = {"Property": 8.9, "Motor": 7.7, "Liability": 9.3, "Marine": 8.7}
SEV_SIG = {"Property": 0.9, "Motor": 0.7, "Liability": 1.0, "Marine": 0.9}
LAG = {"Property": 6, "Motor": 4, "Liability": 30, "Marine": 12}                   # mean report lag (days)
TARGET_LR = {"Property": 0.60, "Motor": 0.70, "Liability": 0.66, "Marine": 0.57}   # calibration level
CAUSES = {
    "Property": (["Fire", "Flood", "Storm/Wind", "Water Damage", "Theft", "Hail"], [22, 12, 20, 22, 16, 8]),
    "Motor": (["Collision", "Theft", "Third-Party PD", "Third-Party BI", "Weather"], [46, 10, 22, 14, 8]),
    "Liability": (["Bodily Injury", "Property Damage", "Professional Error", "Product Liability"], [34, 28, 22, 16]),
    "Marine": (["Cargo Damage", "Cargo Theft", "Vessel Collision", "Heavy Weather"], [38, 16, 18, 28]),
}

# COMMAND ----------

# MAGIC %md ## Policies

# COMMAND ----------

N_POL = 150_000
lob = rng.choice(LOBS, N_POL, p=LOB_W / LOB_W.sum())
region = rng.choice(REGIONS, N_POL, p=REG_W / REG_W.sum())
inception = np.datetime64("2024-01-01") + rng.integers(0, (TODAY - np.datetime64("2024-01-01")).astype(int) - 14, N_POL).astype("timedelta64[D]")
expiry = inception + np.timedelta64(365, "D")
written = np.round(np.exp([rng.normal(PREM_MU[l], 0.8) for l in lob]), 2)

policies = pd.DataFrame({
    "policy_id": [f"POL-{i:07d}" for i in range(1_000_000, 1_000_000 + N_POL)],
    "line_of_business": lob,
    "region": region,
    "broker": rng.choice(BROKERS, N_POL, p=[0.26, 0.24, 0.2, 0.18, 0.12]),
    "inception_date": pd.to_datetime(inception),
    "expiry_date": pd.to_datetime(expiry),
    "written_premium": written,
    "sum_insured": np.round(written * rng.uniform(15, 60, N_POL), 0),
    "underwriting_year": pd.to_datetime(inception).year,
})

# COMMAND ----------

# MAGIC %md ## Earned premium per day (LOB × region × day)

# COMMAND ----------

day0 = START.astype("datetime64[D]")
idx_start = np.clip((inception - day0).astype(int), 0, N_DAYS)
idx_end = np.clip((expiry - day0).astype(int), 0, N_DAYS)          # exclusive
daily = written / 365.0
keys = [(l, r) for l in LOBS for r in REGIONS]
earned_rows = []
for l, r in keys:
    m = (lob == l) & (region == r)
    diff = np.zeros(N_DAYS + 1)
    np.add.at(diff, idx_start[m], daily[m])
    np.add.at(diff, idx_end[m], -daily[m])
    earned = np.cumsum(diff)[:N_DAYS]
    earned_rows.append(pd.DataFrame({"as_of_date": DAYS, "line_of_business": l, "region": r,
                                     "earned_premium": np.round(earned, 2)}))
earned_premium_daily = pd.concat(earned_rows, ignore_index=True)

# COMMAND ----------

# MAGIC %md ## Claims: the loss run (baseline, then the three seeded events)

# COMMAND ----------

def draw_claims(pol_idx, n_per_policy, loss_lo, loss_hi, cause=None, sev=None, large_p=0.001):
    rows = []
    for i, n in zip(pol_idx, n_per_policy):
        l = lob[i]
        for _ in range(int(n)):
            lo = max(loss_lo[i] if np.ndim(loss_lo) else loss_lo, START)
            hi = min(loss_hi[i] if np.ndim(loss_hi) else loss_hi, TODAY)
            if hi <= lo:
                continue
            loss_dt = lo + np.timedelta64(int(rng.integers(0, (hi - lo).astype(int))), "D")
            report_dt = loss_dt + np.timedelta64(int(rng.exponential(LAG[l])), "D")
            if report_dt > TODAY:
                continue
            inc = float(np.exp(rng.normal(*(sev or (SEV_MU[l], SEV_SIG[l])))))
            if rng.random() < large_p:
                inc *= rng.uniform(8, 20)
            c = cause or rng.choice(CAUSES[l][0], p=np.array(CAUSES[l][1]) / sum(CAUSES[l][1]))
            rows.append((policies.policy_id[i], l, region[i], loss_dt, report_dt, c, inc))
    return rows

# baseline: Poisson by exposure inside the observation window
exposure_years = (np.minimum(expiry, TODAY) - np.maximum(inception, START)).astype(int).clip(0) / 365.0
n_claims = rng.poisson([FREQ[l] * e for l, e in zip(lob, exposure_years)])
base = draw_claims(range(N_POL), n_claims, np.maximum(inception, START), np.minimum(expiry, TODAY))
claims = pd.DataFrame(base, columns=["policy_id", "line_of_business", "region", "loss_date",
                                     "report_date", "cause_of_loss", "incurred_loss"])

# calibrate each LOB to a credible baseline loss ratio (shape preserved, level scaled)
ep = earned_premium_daily.groupby("line_of_business").earned_premium.sum()
inc = claims.groupby("line_of_business").incurred_loss.sum()
claims["incurred_loss"] *= claims.line_of_business.map({l: TARGET_LR[l] * ep[l] / inc[l] for l in LOBS})
claims["event_tag"] = None

in_force = lambda l, r: np.where((lob == l) & (region == r) & (inception <= TODAY) & (expiry > TODAY))[0]
scale_of = lambda l: TARGET_LR[l] * ep[l] / inc[l]
T = lambda d: TODAY - np.timedelta64(d, "D")

# Event 1: hailstorm, DACH Property. ~420 claims with loss dates T-6..T-2, average ~EUR 45k, a handful above EUR 250k
p = rng.choice(in_force("Property", "DACH"), 420, replace=False)
ev1 = pd.DataFrame(draw_claims(p, np.ones(len(p)), T(6), T(1), cause="Hail", sev=(10.45, 0.75), large_p=0.0),
                   columns=claims.columns[:7])
ev1["event_tag"] = "Hailstorm DACH"

# Event 2: frequency creep, UK & Ireland Motor. 45% more collisions over the last 21 days at normal severity
p = in_force("Motor", "UK & Ireland")
n_extra = rng.poisson(0.45 * 21 * len(p) * FREQ["Motor"] / 365)
ev2 = pd.DataFrame(draw_claims(rng.choice(p, n_extra), np.ones(n_extra), T(21), TODAY, cause="Collision", large_p=0.0),
                   columns=claims.columns[:7])
ev2["incurred_loss"] *= scale_of("Motor"); ev2["event_tag"] = "Motor frequency creep"

# Event 3: one large bodily-injury loss, Southern Europe Liability, reported T-3
i = int(rng.choice(in_force("Liability", "Southern Europe")))
ev3 = pd.DataFrame([(policies.policy_id[i], "Liability", "Southern Europe", T(9), T(3), "Bodily Injury", 2_400_000.0)],
                   columns=claims.columns[:7])
ev3["event_tag"] = "Large BI loss"

claims = pd.concat([claims, ev1, ev2, ev3], ignore_index=True)

# paid / reserve / recovery / status
age = (TODAY - claims.report_date.values.astype("datetime64[D]")).astype(int)
p_closed = np.clip(0.2 + age / 400 - np.where(claims.line_of_business == "Liability", 0.25, 0), 0.05, 0.95)
closed = rng.random(len(claims)) < p_closed
claims["incurred_loss"] = claims.incurred_loss.round(2)
claims["paid_loss"] = np.where(closed, claims.incurred_loss, (claims.incurred_loss * rng.uniform(0.05, 0.6, len(claims))).round(2))
claims["case_reserve"] = (claims.incurred_loss - claims.paid_loss).round(2)
claims["claim_status"] = np.where(closed, "Closed", "Open")
rec = claims.cause_of_loss.isin(["Theft", "Cargo Theft", "Third-Party PD", "Vessel Collision", "Property Damage"])
claims["recovery_amount"] = np.where(rec & (rng.random(len(claims)) < 0.4), (claims.incurred_loss * rng.uniform(0.05, 0.3, len(claims))).round(2), 0.0)
claims["large_loss_flag"] = claims.incurred_loss >= 250_000
claims["cat_event_flag"] = claims.event_tag.eq("Hailstorm DACH")
claims = claims.sort_values("report_date").reset_index(drop=True)
claims.insert(0, "claim_id", [f"CLM-{i:07d}" for i in range(3_000_000, 3_000_000 + len(claims))])
claims["loss_date"] = pd.to_datetime(claims.loss_date).dt.date
claims["report_date"] = pd.to_datetime(claims.report_date).dt.date
earned_premium_daily["as_of_date"] = earned_premium_daily.as_of_date.dt.date
policies["inception_date"] = policies.inception_date.dt.date
policies["expiry_date"] = policies.expiry_date.dt.date

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

# MAGIC %md
# MAGIC ## Land the files

# COMMAND ----------

import json
import os
import random
from datetime import timedelta

random.seed(7)
rng_files = np.random.default_rng(7)
for folder in ["claims_fnol", "premium_bordereaux"]:
    dbutils.fs.rm(f"{RAW}/{folder}", True)            # a clean landing zone on every run

# land this year only: the book above is calibrated on the full history, so recent loss ratios are unchanged
from datetime import date
land_from = min(date(date.today().year, 1, 1), date.today() - timedelta(days=180))
claims = claims[claims.report_date >= land_from].reset_index(drop=True)
earned_premium_daily = earned_premium_daily[earned_premium_daily.as_of_date >= land_from].reset_index(drop=True)
print(f"Landing claims and premium from {land_from}: {len(claims):,} claims, {len(earned_premium_daily):,} premium rows")

last = max(claims.report_date.max(), earned_premium_daily.as_of_date.max())
daily_from = last - timedelta(days=DAILY_DROP_DAYS - 1)
drop_of = lambda d: d.isoformat() if d >= daily_from else d.strftime("%Y-%m")

stats = {"claims": 0, "files": 0, "mismatch": 0, "pii": 0, "neg": 0, "dates": 0, "dupes": 0, "ccy": 0}
drops = {}
for r in claims.itertuples(index=False):
    cause = r.cause_of_loss
    rec = {"claim_id": r.claim_id, "policy_id": r.policy_id, "line_of_business": r.line_of_business, "region": r.region,
           "loss_date": str(r.loss_date), "report_date": str(r.report_date), "cause_of_loss": cause,
           "incurred_loss": round(float(r.incurred_loss), 2), "paid_loss": round(float(r.paid_loss), 2),
           "case_reserve": round(float(r.case_reserve), 2), "claim_status": r.claim_status, "currency": "EUR",
           "event_tag": r.event_tag, "loss_description": describe(cause, r.region),
           "source_system": random.choice(["ClaimsHub", "BrokerPortal", "FNOL-App"])}
    u = rng_files.random()
    if u < 0.02 and cause in WRONG:                       # code contradicts the narrative
        rec["cause_of_loss"] = WRONG[cause]; stats["mismatch"] += 1
    elif u < 0.05:                                        # personal data typed into free text
        n = random.choice(NAMES)
        rec["loss_description"] += f". Contact {n} on +44 7700 {rng_files.integers(100000, 999999)} or {n.split()[0].lower()}@example.com"
        stats["pii"] += 1
    elif u < 0.053:
        rec["incurred_loss"] = -abs(rec["incurred_loss"]); stats["neg"] += 1
    elif u < 0.056:
        rec["report_date"] = str(r.report_date + timedelta(days=int(rng_files.integers(3, 30)))); stats["dates"] += 1
    elif u < 0.061:
        rec["currency"] = "GBP"; stats["ccy"] += 1
    drops.setdefault(drop_of(r.report_date), []).append(rec)
    if rng_files.random() < 0.01:                         # resent later: the pipeline must de-duplicate it
        later = drop_of(min(r.report_date + timedelta(days=1), last))
        drops.setdefault(later, []).append(dict(rec)); stats["dupes"] += 1

for key in sorted(drops):
    recs = drops[key]
    random.shuffle(recs)
    path = f"{RAW}/claims_fnol/{key}"
    os.makedirs(path, exist_ok=True)
    parts = FILES_PER_DAY if len(key) == 10 else 1
    for b, chunk in enumerate(np.array_split(np.arange(len(recs)), parts)):
        with open(f"{path}/fnol_{key}_{b + 1:02d}.json", "w") as fh:
            for i in chunk:
                fh.write(json.dumps(recs[i]) + "\n")
        stats["files"] += 1
    stats["claims"] += len(recs)

prem = earned_premium_daily.copy()
prem["drop"] = prem.as_of_date.map(drop_of)
prem["currency"] = "EUR"
for key, p in prem.groupby("drop"):
    p = p.copy()
    p["bordereau_id"] = [f"BDX-{key}-{i:04d}" for i in range(len(p))]
    if len(key) == 10 and rng_files.random() < 0.2:      # an occasional sign error from a broker
        p.loc[p.index[0], "earned_premium"] *= -1
    path = f"{RAW}/premium_bordereaux/{key}"
    os.makedirs(path, exist_ok=True)
    p[["bordereau_id", "as_of_date", "line_of_business", "region", "earned_premium", "currency"]].to_csv(
        f"{path}/premium_{key}.csv", index=False)
    stats["files"] += 1

print(f"Landed {stats['claims']:,} claim records and {len(prem):,} premium rows in {stats['files']} files under {RAW}")
print(f"Planted events: {len(ev1)} hail, {len(ev2)} motor, {len(ev3)} large BI · defects: " + json.dumps(
    {k: v for k, v in stats.items() if k not in ("claims", "files")}))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Answer key for the optional evaluation
# MAGIC The true cause of loss per claim, before the planted code errors. Only `optional/evaluate_genai_dq` reads it.

# COMMAND ----------

(spark.createDataFrame(claims[["claim_id", "line_of_business", "region", "report_date", "cause_of_loss"]])
     .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{FQ}.truth_claims"))
spark.sql(f"COMMENT ON TABLE {FQ}.truth_claims IS 'Answer key: true cause of loss per synthetic claim, for the optional Gen AI evaluation only.'")
display(dbutils.fs.ls(f"{RAW}/claims_fnol")[-5:])
