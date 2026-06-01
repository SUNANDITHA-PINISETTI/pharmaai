import pandas as pd
import numpy as np
from sqlalchemy import create_engine

# ===============================
# 🔥 STEP 1: LOAD DATA FROM MYSQL
# ===============================
engine = create_engine("mysql+mysqlconnector://sunanditha:1234@localhost/production_db")

df = pd.read_sql("SELECT * FROM production_table", engine)

print("✅ Data Loaded")
print("Shape:", df.shape)


# ===============================
# 🔥 STEP 2: CONVERT TO NUMERIC
# ===============================
df_numeric = df.copy()

for col in df_numeric.columns:
    df_numeric[col] = pd.to_numeric(df_numeric[col], errors='coerce')

df_numeric = df_numeric.dropna(axis=1, how='all')
df_numeric = df_numeric.fillna(0)

print("Numeric columns:", df_numeric.columns)


# ===============================
# 🔥 STEP 3: SCALING
# ===============================
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X = scaler.fit_transform(df_numeric)


# ===============================
# 🔥 STEP 4: ML MODELS
# ===============================
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM

# Isolation Forest
iso_model = IsolationForest(contamination=0.05, random_state=42)
df["iso_error"] = iso_model.fit_predict(X)
df["iso_error"] = df["iso_error"].apply(lambda x: 1 if x == -1 else 0)

# LOF
lof = LocalOutlierFactor(n_neighbors=20, contamination=0.05)
lof_pred = lof.fit_predict(X)
df["lof_error"] = [1 if x == -1 else 0 for x in lof_pred]

# One-Class SVM
svm = OneClassSVM(nu=0.05, kernel="rbf", gamma="scale")
svm_pred = svm.fit_predict(X)
df["svm_error"] = [1 if x == -1 else 0 for x in svm_pred]


# ===============================
# 🔥 STEP 5: STATISTICAL METHODS
# ===============================
# Z-score
std = df_numeric.std().replace(0, 1)
z_scores = np.abs((df_numeric - df_numeric.mean()) / std)
df["zscore_error"] = (z_scores > 3).any(axis=1).astype(int)

# IQR
Q1 = df_numeric.quantile(0.25)
Q3 = df_numeric.quantile(0.75)
IQR = Q3 - Q1
iqr_mask = ((df_numeric < (Q1 - 1.5 * IQR)) | (df_numeric > (Q3 + 1.5 * IQR)))
df["iqr_error"] = iqr_mask.any(axis=1).astype(int)


# ===============================
# 🔥 STEP 6: SEQUENCE DETECTION
# ===============================
df["sequence_error"] = 0

for col in df_numeric.columns:
    diff = df_numeric[col].diff().fillna(0)
    threshold = diff.mean() + 2 * diff.std()
    df["sequence_error"] |= (abs(diff) > threshold).astype(int)


# ===============================
# 🔥 STEP 7: FINAL ENSEMBLE
# ===============================
df["total_votes"] = (
    df["iso_error"] +
    df["lof_error"] +
    df["svm_error"] +
    df["zscore_error"] +
    df["iqr_error"] +
    df["sequence_error"]
)

df["final_error"] = df["total_votes"].apply(
    lambda x: "Error" if x >= 2 else "Normal"
)


# ===============================
# 🔥 STEP 8: HUMAN JUSTIFICATION
# ===============================
def explain_error(row):
    reasons = []

    if row["zscore_error"]:
        reasons.append("Extreme value detected")

    if row["iqr_error"]:
        reasons.append("Value outside acceptable range")

    if row["sequence_error"]:
        reasons.append("Sequence break in process")

    if row["iso_error"] or row["lof_error"] or row["svm_error"]:
        reasons.append("Unusual production pattern")

    return ", ".join(reasons) if reasons else "Normal"


df["justification"] = df.apply(explain_error, axis=1)


# ===============================
# 🔥 STEP 9: STAGE MAPPING
# ===============================
def map_stage(col):
    c = col.lower()

    if "raw" in c or "material" in c:
        return "Dispensing"
    elif "gran" in c or "mix" in c:
        return "Granulation"
    elif "dry" in c or "moisture" in c:
        return "Drying"
    elif "blend" in c:
        return "Blending"
    elif any(x in c for x in ["tablet", "compression", "force", "rpm", "counter", "running"]):
        return "Compression"
    elif any(x in c for x in ["coat", "spray", "temp"]):
        return "Coating"
    elif any(x in c for x in ["pack", "label"]):
        return "Packing"
    elif any(x in c for x in ["time", "storage", "hold"]):
        return "WIP"
    else:
        return "Other"


def detect_stage(row):
    stages = set()

    for col in df_numeric.columns:
        if (
            row["zscore_error"] or
            row["iqr_error"] or
            row["sequence_error"]
        ):
            stages.add(map_stage(col))

    return ", ".join(stages) if stages else "No Stage"


df["stage"] = df.apply(detect_stage, axis=1)


# ===============================
# 🔥 STEP 10: SAVE TO MYSQL
# ===============================
df.to_sql("production_ml_results", con=engine, if_exists="replace", index=False)

print("\n✅ DONE: ML + Stage Mapping Completed")